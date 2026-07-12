from __future__ import annotations

import json
import math
import random
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from src.domain.dataset.dataset_source import DatasetSource
from src.domain.dataset.feedback_type import FeedbackType
from src.domain.dto.dataset.training_example import TrainingExample
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_dataset_candidate import ModerationDatasetCandidate
from src.training.datasets.moderation_dataset_mix_config import ModerationDatasetMixConfig
from src.training.datasets.moderation_export_relabeler import ModerationExportRelabeler
from src.training.datasets.hard_eval_pack import build_hard_eval_pack
from src.training.datasets.moderation_label_priority import resolve_primary_label
from src.training.datasets.moderation_public_dataset_loaders import (
    DiscordRawMessageLoader,
    HuggingFaceSafeTextLoader,
    HuggingFaceSpamLoader,
    HuggingFaceToxicityLoader,
    HuggingFaceUrlSecurityLoader,
    LocalCuratedDatasetLoader,
    ProjectTrainingExampleLoader,
)
from src.training.datasets.synthetic_discord_examples import (
    build_ai_generated_edge_candidates,
    build_contextual_contrast_candidates,
    build_manual_synthetic_candidates,
)
from src.training.datasets.russian_robustness_examples import build_russian_robustness_candidates
from src.training.datasets.quota_backfill_examples import build_quota_backfill_candidates
from src.training.datasets.russian_slang_examples import build_russian_slang_candidates
from src.training.datasets.training_text_sanitizer import TrainingTextSanitizer
from src.training.datasets.unseen_hard_eval_pack import build_unseen_hard_eval_pack
from src.training.rubert.rubert_dataset_builder import RuBertDatasetBuilder
from src.training.rubert.rubert_training_config import RuBertTrainingConfig


class ModerationDatasetAssembler:
    def __init__(
        self,
        config: ModerationDatasetMixConfig,
        *,
        rubert_config: RuBertTrainingConfig | None = None,
    ) -> None:
        self._config = config
        self._rubert_config = rubert_config or RuBertTrainingConfig.load()
        self._random = random.Random(config.dataset.random_seed)
        self._sanitizer = TrainingTextSanitizer()
        self._relabeler = ModerationExportRelabeler(self._rubert_config.label_schema)
        evaluation_rows = [*build_hard_eval_pack(), *build_unseen_hard_eval_pack()]
        self._evaluation_texts = {self._sanitizer.sanitize(str(row["text"])) for row in evaluation_rows}

    def build(self, *, strict: bool | None = None) -> dict:
        use_strict = self._config.dataset.strict if strict is None else strict
        source_quotas = self._config.source_quotas()
        started_at = time.monotonic()
        filtered_checkpoint = self._checkpoint_path("filtered")
        raw_checkpoint = self._checkpoint_path("raw")
        load_errors: dict[str, str] = {}

        if self._config.dataset.reuse_checkpoints and filtered_checkpoint.exists():
            candidates = self._load_checkpoint(filtered_checkpoint)
            self._report_progress("resumed_filtered", candidates_after_filter=len(candidates))
        else:
            if self._config.dataset.reuse_checkpoints and raw_checkpoint.exists():
                candidates = self._load_checkpoint(raw_checkpoint)
                self._report_progress("resumed_raw", candidates_loaded=len(candidates))
            else:
                self._report_progress("loading_sources", enabled_sources=sum(spec.enabled for spec in self._config.sources.values()))
                candidates, load_errors = self._load_candidates(source_quotas)
                self._save_checkpoint(raw_checkpoint, candidates)
            self._report_progress("filtering", candidates_loaded=len(candidates), elapsed_seconds=round(time.monotonic() - started_at, 1))
            candidates = self._quality_filter(candidates)
            self._save_checkpoint(filtered_checkpoint, candidates)
        self._report_progress("selecting", candidates_after_filter=len(candidates), elapsed_seconds=round(time.monotonic() - started_at, 1))
        selected, shortfalls = self._select_candidates(candidates, source_quotas)

        label_shortfalls = {key: value for key, value in shortfalls.items() if key.startswith("label:")}
        if use_strict and label_shortfalls:
            raise RuntimeError(f"Dataset quotas were not satisfied: {shortfalls}")

        examples = [self._to_training_example(candidate, index) for index, candidate in enumerate(selected)]
        self._report_progress("writing_splits", selected_examples=len(examples), elapsed_seconds=round(time.monotonic() - started_at, 1))
        split_examples = self._split_examples(examples)
        self._write_exports(split_examples)
        manifest = self._build_manifest(examples, split_examples, source_quotas, shortfalls, load_errors)
        manifest_path = self._config.dataset.output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self._report_progress("complete", actual_total=len(examples), elapsed_seconds=round(time.monotonic() - started_at, 1))
        return manifest

    def _report_progress(self, stage: str, **details: object) -> None:
        """Expose build state both in the terminal and in a small pollable file."""
        output_dir = self._config.dataset.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        progress = {"stage": stage, "updated_at": datetime.now(timezone.utc).isoformat(), **details}
        (output_dir / "build_progress.json").write_text(
            json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        detail_text = " ".join(f"{key}={value}" for key, value in details.items())
        print(f"[dataset] stage={stage} {detail_text}".rstrip(), flush=True)

    def _checkpoint_path(self, stage: str) -> Path:
        return self._config.dataset.output_dir / f"candidates_{stage}_{self._config.dataset.checkpoint_version}.jsonl"

    @staticmethod
    def _save_checkpoint(path: Path, candidates: list[ModerationDatasetCandidate]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(".tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            for candidate in candidates:
                file.write(candidate.model_dump_json() + "\n")
        temporary_path.replace(path)
        print(f"[dataset] checkpoint_saved path={path} candidates={len(candidates)}", flush=True)

    @staticmethod
    def _load_checkpoint(path: Path) -> list[ModerationDatasetCandidate]:
        with path.open("r", encoding="utf-8") as file:
            candidates = [ModerationDatasetCandidate.model_validate_json(line) for line in file if line.strip()]
        print(f"[dataset] checkpoint_loaded path={path} candidates={len(candidates)}", flush=True)
        return candidates

    def _load_candidates(self, source_quotas: dict[str, int]) -> tuple[list[ModerationDatasetCandidate], dict[str, str]]:
        candidates: list[ModerationDatasetCandidate] = []
        errors: dict[str, str] = {}
        sources = self._config.sources
        # Existing loaders historically multiply their requested quota by three.
        # Rescale their input once here so a large build does not scan millions of
        # rows before it can apply the configured deduplication and class quotas.
        source_quotas = {
            source: max(1, math.ceil(quota * self._config.dataset.candidate_load_multiplier / 3))
            for source, quota in source_quotas.items()
        }

        if sources.get("project") and sources["project"].enabled:
            print("[dataset] source=project", flush=True)
            path = Path(str(getattr(sources["project"], "path", "data/exports/project_training_examples.jsonl")))
            candidates.extend(ProjectTrainingExampleLoader().load(path))

        if sources.get("project_raw") and sources["project_raw"].enabled:
            print("[dataset] source=project_raw", flush=True)
            path = Path(str(getattr(sources["project_raw"], "path", "data/raw/discord_messages.jsonl")))
            candidates.extend(
                DiscordRawMessageLoader().load(
                    path,
                    limit=max(source_quotas.get("project_raw", 0) * 2, 100),
                )
            )

        local_tasks: list[tuple[str, Callable[[], list[ModerationDatasetCandidate]]]] = []
        for source_name in ("russian_discord_chat_logs", "russian_telegram_chat_logs"):
            if sources.get(source_name) and sources[source_name].enabled:
                spec = sources[source_name]
                local_path = Path(str(getattr(spec, "local_path", "")))
                local_tasks.append((source_name, lambda name=source_name, path=local_path: LocalCuratedDatasetLoader().load_chat_log_parquet(
                    path, source_bucket=name, limit=max(source_quotas.get(name, 0) * 3, 100),
                )))
        if sources.get("russian_dialogues_2") and sources["russian_dialogues_2"].enabled:
            spec = sources["russian_dialogues_2"]
            local_tasks.append(("russian_dialogues_2", lambda path=Path(str(getattr(spec, "local_path", ""))): LocalCuratedDatasetLoader().load_dialogues_gzip(
                path, source_bucket="russian_dialogues_2", limit=max(source_quotas.get("russian_dialogues_2", 0) * 3, 100),
            )))
        if sources.get("russian_tiny_conversations") and sources["russian_tiny_conversations"].enabled:
            spec = sources["russian_tiny_conversations"]
            local_tasks.append(("russian_tiny_conversations", lambda path=Path(str(getattr(spec, "local_path", ""))): LocalCuratedDatasetLoader().load_tiny_conversations(
                path, limit=max(source_quotas.get("russian_tiny_conversations", 0) * 3, 100),
            )))
        if sources.get("hard_toxic_real") and sources["hard_toxic_real"].enabled:
            spec = sources["hard_toxic_real"]
            local_tasks.append(("hard_toxic_real", lambda path=Path(str(getattr(spec, "local_path", ""))): LocalCuratedDatasetLoader().load_hard_sensitive_topics(
                path, limit=max(source_quotas.get("hard_toxic_real", 0) * 3, 100),
            )))
        if sources.get("hard_nsfw_real") and sources["hard_nsfw_real"].enabled:
            spec = sources["hard_nsfw_real"]
            local_tasks.append(("hard_nsfw_real", lambda path=Path(str(getattr(spec, "local_path", ""))): LocalCuratedDatasetLoader().load_hard_sensitive_nsfw(
                path, limit=max(source_quotas.get("hard_nsfw_real", 0) * 3, 100),
            )))
        loaded_local, local_errors = self._load_sources_parallel(local_tasks)
        candidates.extend(loaded_local)
        errors.update(local_errors)

        if sources.get("russian_toxicity") and sources["russian_toxicity"].enabled:
            print("[dataset] source=russian_toxicity", flush=True)
            spec = sources["russian_toxicity"]
            try:
                local_path = Path(str(getattr(spec, "local_path", "")))
                candidates.extend(
                    LocalCuratedDatasetLoader().load_parquet_binary(
                        local_path, source_bucket="russian_toxicity",
                        limit=max(source_quotas.get("russian_toxicity", 0) * 3, 100),
                        text_keys=("text",), label_key="toxic", positive_label=ModerationLabel.TOXIC,
                    ) if local_path.exists() else HuggingFaceToxicityLoader().load_textdetox_ru(
                        str(getattr(spec, "dataset_id")), str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_toxicity", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_toxicity"] = str(exc)

        if sources.get("russian_toxic_comments") and sources["russian_toxic_comments"].enabled:
            print("[dataset] source=russian_toxic_comments", flush=True)
            spec = sources["russian_toxic_comments"]
            try:
                local_path = Path(str(getattr(spec, "local_path", "")))
                candidates.extend(
                    LocalCuratedDatasetLoader().load_binary_jsonl(
                        local_path,
                        source_bucket="russian_toxic_comments",
                        limit=max(source_quotas.get("russian_toxic_comments", 0) * 3, 100),
                    )
                    if local_path.exists()
                    else HuggingFaceToxicityLoader().load_binary_toxicity_dataset(
                        str(getattr(spec, "dataset_id")), str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_toxic_comments", 0) * 3, 100),
                        source_bucket="russian_toxic_comments",
                    )
                )
            except Exception as exc:
                errors["russian_toxic_comments"] = str(exc)

        if sources.get("russian_toxic_merged") and sources["russian_toxic_merged"].enabled:
            print("[dataset] source=russian_toxic_merged", flush=True)
            spec = sources["russian_toxic_merged"]
            try:
                candidates.extend(
                    HuggingFaceToxicityLoader().load_binary_toxicity_dataset(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_toxic_merged", 0) * 3, 100),
                        source_bucket="russian_toxic_merged",
                    )
                )
            except Exception as exc:
                errors["russian_toxic_merged"] = str(exc)

        if sources.get("russian_inappropriate") and sources["russian_inappropriate"].enabled:
            print("[dataset] source=russian_inappropriate", flush=True)
            spec = sources["russian_inappropriate"]
            try:
                local_path = Path(str(getattr(spec, "local_path", "")))
                candidates.extend(
                    LocalCuratedDatasetLoader().load_inappropriate_csv(
                        local_path, source_bucket="russian_inappropriate",
                        limit=max(source_quotas.get("russian_inappropriate", 0) * 3, 100),
                        toxic_threshold=float(getattr(spec, "toxic_threshold", 0.75)),
                        safe_threshold=float(getattr(spec, "safe_threshold", 0.25)),
                    ) if local_path.exists() else HuggingFaceToxicityLoader().load_inappropriateness_dataset(
                        str(getattr(spec, "dataset_id")), str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_inappropriate", 0) * 3, 100),
                        toxic_threshold=float(getattr(spec, "toxic_threshold", 0.75)),
                        safe_threshold=float(getattr(spec, "safe_threshold", 0.25)),
                    )
                )
            except Exception as exc:
                errors["russian_inappropriate"] = str(exc)

        if sources.get("russian_nsfw_benchmark") and sources["russian_nsfw_benchmark"].enabled:
            spec = sources["russian_nsfw_benchmark"]
            try:
                candidates.extend(
                    HuggingFaceToxicityLoader().load_redmadrobot_nsfw_benchmark(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_nsfw_benchmark", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_nsfw_benchmark"] = str(exc)

        if sources.get("russian_nsfw_fiction") and sources["russian_nsfw_fiction"].enabled:
            spec = sources["russian_nsfw_fiction"]
            try:
                local_path = Path(str(getattr(spec, "local_path", "")))
                candidates.extend(
                    LocalCuratedDatasetLoader().load_nsfw_parquet(
                        local_path, source_bucket="russian_nsfw_fiction",
                        limit=max(source_quotas.get("russian_nsfw_fiction", 0) * 3, 100),
                    ) if local_path.exists() else HuggingFaceToxicityLoader().load_nsfw_fiction_dataset(
                        str(getattr(spec, "dataset_id")), str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_nsfw_fiction", 0) * 3, 100),
                        source_bucket="russian_nsfw_fiction",
                    )
                )
            except Exception as exc:
                errors["russian_nsfw_fiction"] = str(exc)

        if sources.get("russian_toxic_dvach") and sources["russian_toxic_dvach"].enabled:
            print("[dataset] source=russian_toxic_dvach", flush=True)
            spec = sources["russian_toxic_dvach"]
            try:
                local_path = Path(str(getattr(spec, "local_path", "")))
                candidates.extend(
                    LocalCuratedDatasetLoader().load_binary_csv(
                        local_path,
                        source_bucket="russian_toxic_dvach",
                        limit=max(source_quotas.get("russian_toxic_dvach", 0) * 3, 100),
                    )
                    if local_path.exists()
                    else HuggingFaceToxicityLoader().load_toxic_dvach_dataset(
                        str(getattr(spec, "dataset_id")), str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_toxic_dvach", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_toxic_dvach"] = str(exc)

        if sources.get("russian_paradetox") and sources["russian_paradetox"].enabled:
            spec = sources["russian_paradetox"]
            try:
                candidates.extend(
                    HuggingFaceToxicityLoader().load_paradetox_ru_dataset(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_paradetox", 0) * 3, 100),
                        source_bucket="russian_paradetox",
                    )
                )
            except Exception as exc:
                errors["russian_paradetox"] = str(exc)

        if sources.get("russian_react_hate") and sources["russian_react_hate"].enabled:
            print("[dataset] source=russian_react_hate", flush=True)
            spec = sources["russian_react_hate"]
            raw_splits = getattr(spec, "splits", ("rus_lgbtq", "rus_war"))
            splits = tuple(str(split) for split in raw_splits)
            try:
                local_paths = [Path(str(path)) for path in getattr(spec, "local_paths", ())]
                candidates.extend(
                    LocalCuratedDatasetLoader().load_react_hate(
                        local_paths, source_bucket="russian_react_hate",
                        limit=max(source_quotas.get("russian_react_hate", 0) * 3, 100),
                    ) if local_paths and all(path.exists() for path in local_paths) else HuggingFaceToxicityLoader().load_react_hate_dataset(
                        str(getattr(spec, "dataset_id")), splits,
                        limit=max(source_quotas.get("russian_react_hate", 0) * 3, 100), source_bucket="russian_react_hate",
                    )
                )
            except Exception as exc:
                errors["russian_react_hate"] = str(exc)

        if sources.get("russian_dialogues_safe") and sources["russian_dialogues_safe"].enabled:
            print("[dataset] source=russian_dialogues_safe", flush=True)
            spec = sources["russian_dialogues_safe"]
            try:
                candidates.extend(
                    HuggingFaceSafeTextLoader().load_dialogues_relabelled(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_dialogues_safe", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_dialogues_safe"] = str(exc)

        if sources.get("russian_literature_safe") and sources["russian_literature_safe"].enabled:
            print("[dataset] source=russian_literature_safe", flush=True)
            spec = sources["russian_literature_safe"]
            try:
                local_path = Path(str(getattr(spec, "local_path", "")))
                candidates.extend(
                    LocalCuratedDatasetLoader().load_literature_safe(
                        local_path,
                        source_bucket="russian_literature_safe",
                        limit=max(source_quotas.get("russian_literature_safe", 0) * 3, 100),
                    )
                    if local_path.exists()
                    else HuggingFaceSafeTextLoader().load_literature_safe(
                        str(getattr(spec, "dataset_id")), str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_literature_safe", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_literature_safe"] = str(exc)

        if sources.get("russian_dialogsum_safe") and sources["russian_dialogsum_safe"].enabled:
            spec = sources["russian_dialogsum_safe"]
            try:
                local_path = Path(str(getattr(spec, "local_path", "")))
                candidates.extend(
                    LocalCuratedDatasetLoader().load_dialogue_safe(
                        local_path, source_bucket="russian_dialogsum_safe",
                        limit=max(source_quotas.get("russian_dialogsum_safe", 0) * 3, 100),
                    ) if local_path.exists() else HuggingFaceSafeTextLoader().load_dialogsum_safe(
                        str(getattr(spec, "dataset_id")), str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_dialogsum_safe", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_dialogsum_safe"] = str(exc)

        if sources.get("russian_kinship_hard_safe") and sources["russian_kinship_hard_safe"].enabled:
            spec = sources["russian_kinship_hard_safe"]
            raw_datasets = getattr(spec, "datasets", ())
            datasets = [dict(item) for item in raw_datasets]
            try:
                candidates.extend(
                    HuggingFaceSafeTextLoader().load_kinship_hard_safe(
                        datasets,
                        limit=max(source_quotas.get("russian_kinship_hard_safe", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_kinship_hard_safe"] = str(exc)

        if sources.get("russian_spam") and sources["russian_spam"].enabled:
            print("[dataset] source=russian_spam", flush=True)
            spec = sources["russian_spam"]
            try:
                local_path = Path(str(getattr(spec, "local_path", "")))
                candidates.extend(
                    LocalCuratedDatasetLoader().load_spam_parquet(
                        local_path,
                        source_bucket="russian_spam",
                        limit=max(source_quotas.get("russian_spam", 0) * 3, 100),
                    )
                    if local_path.exists()
                    else HuggingFaceSpamLoader().load_spam_dataset(
                        str(getattr(spec, "dataset_id")), str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_spam", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_spam"] = str(exc)

        if sources.get("russian_spam_fork") and sources["russian_spam_fork"].enabled:
            spec = sources["russian_spam_fork"]
            try:
                local_path = Path(str(getattr(spec, "local_path", "")))
                candidates.extend(
                    LocalCuratedDatasetLoader().load_spam_parquet(
                        local_path, source_bucket="russian_spam_fork",
                        limit=max(source_quotas.get("russian_spam_fork", 0) * 3, 100),
                    ) if local_path.exists() else HuggingFaceSpamLoader().load_spam_dataset(
                        str(getattr(spec, "dataset_id")), str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_spam_fork", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_spam_fork"] = str(exc)

        if sources.get("russian_scam_spam_public") and sources["russian_scam_spam_public"].enabled:
            print("[dataset] source=russian_scam_spam_public", flush=True)
            spec = sources["russian_scam_spam_public"]
            try:
                candidates.extend(
                    HuggingFaceSpamLoader().load_russian_scam_spam_dataset(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_scam_spam_public", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_scam_spam_public"] = str(exc)

        if sources.get("hard_scam_real") and sources["hard_scam_real"].enabled:
            print("[dataset] source=hard_scam_real", flush=True)
            spec = sources["hard_scam_real"]
            try:
                candidates.extend(LocalCuratedDatasetLoader().load_fraudlens(
                    Path(str(getattr(spec, "local_path", ""))),
                    limit=max(source_quotas.get("hard_scam_real", 0) * 3, 100),
                ))
            except Exception as exc:
                errors["hard_scam_real"] = str(exc)

        if sources.get("phishing_url") and sources["phishing_url"].enabled:
            print("[dataset] source=phishing_url", flush=True)
            spec = sources["phishing_url"]
            try:
                candidates.extend(
                    HuggingFaceUrlSecurityLoader().load_malicious_url_dataset(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
                        limit=max(source_quotas.get("phishing_url", 0) * 3, 100),
                        source_bucket="phishing_url",
                    )
                )
            except Exception as exc:
                errors["phishing_url"] = str(exc)

        if sources.get("discord_phishing_scam") and sources["discord_phishing_scam"].enabled:
            print("[dataset] source=discord_phishing_scam", flush=True)
            spec = sources["discord_phishing_scam"]
            try:
                candidates.extend(
                    HuggingFaceUrlSecurityLoader().load_discord_phishing_scam_dataset(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
                        limit=max(source_quotas.get("discord_phishing_scam", 0) * 3, 100),
                        source_bucket="discord_phishing_scam",
                    )
                )
            except Exception as exc:
                errors["discord_phishing_scam"] = str(exc)

        if sources.get("manual_synthetic") and sources["manual_synthetic"].enabled:
            manual_templates = build_manual_synthetic_candidates()
            candidates.extend(manual_templates)

        if sources.get("contextual_contrast") and sources["contextual_contrast"].enabled:
            candidates.extend(build_contextual_contrast_candidates())

        if sources.get("ai_generated_edge") and sources["ai_generated_edge"].enabled:
            edge_templates = build_ai_generated_edge_candidates()
            candidates.extend(edge_templates)

        if sources.get("russian_robustness") and sources["russian_robustness"].enabled:
            print("[dataset] source=russian_robustness", flush=True)
            candidates.extend(build_russian_robustness_candidates())

        # Last-resort class-balanced examples are intentionally added after
        # public and project data.  They fill documented long-tail shortages
        # without changing the source priority of real conversations.
        print("[dataset] source=quota_backfill", flush=True)
        candidates.extend(build_quota_backfill_candidates())
        print("[dataset] source=russian_slang", flush=True)
        candidates.extend(build_russian_slang_candidates())

        self._random.shuffle(candidates)
        return candidates, errors

    def _load_sources_parallel(
        self,
        tasks: list[tuple[str, Callable[[], list[ModerationDatasetCandidate]]]],
    ) -> tuple[list[ModerationDatasetCandidate], dict[str, str]]:
        """Load independent local sources concurrently, then merge in stable order."""
        if not tasks:
            return [], {}
        print(f"[dataset] parallel_sources workers={min(self._config.dataset.source_workers, len(tasks))} tasks={len(tasks)}", flush=True)
        results: dict[str, list[ModerationDatasetCandidate]] = {}
        errors: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=min(self._config.dataset.source_workers, len(tasks)), thread_name_prefix="dataset-source") as executor:
            futures = {source: executor.submit(loader) for source, loader in tasks}
            for source, _ in tasks:
                try:
                    results[source] = futures[source].result()
                    print(f"[dataset] source={source} candidates={len(results[source])}", flush=True)
                except Exception as exc:
                    errors[source] = str(exc)
        merged: list[ModerationDatasetCandidate] = []
        for source, _ in tasks:
            merged.extend(results.get(source, []))
        return merged, errors

    def _quality_filter(
        self,
        candidates: list[ModerationDatasetCandidate],
    ) -> list[ModerationDatasetCandidate]:
        seen: set[str] = set()
        filtered: list[ModerationDatasetCandidate] = []
        for candidate in candidates:
            model_text = self._sanitizer.sanitize(candidate.text)
            if len(model_text) < self._config.quality.min_text_length:
                continue
            if len(model_text) > self._config.quality.max_text_length:
                model_text = model_text[: self._config.quality.max_text_length].strip()
            if model_text in self._evaluation_texts:
                continue
            if self._config.quality.deduplicate_by_text and model_text in seen:
                continue
            seen.add(model_text)
            relabeled = self._relabeler.relabel_row(
                {
                    "model_text": model_text,
                    "labels": [label.value for label in candidate.labels],
                    "primary_label": candidate.primary_label.value,
                    "severity": candidate.severity,
                }
            )
            labels = [ModerationLabel(label) for label in relabeled.get("labels", [])]
            primary_label = ModerationLabel(str(relabeled.get("primary_label") or candidate.primary_label.value))
            filtered.append(candidate.model_copy(update={
                "text": model_text,
                "labels": labels or [primary_label],
                "primary_label": primary_label,
                "severity": int(relabeled.get("severity") or candidate.severity),
            }))
        return filtered

    def _select_candidates(
        self,
        candidates: list[ModerationDatasetCandidate],
        source_quotas: dict[str, int],
    ) -> tuple[list[ModerationDatasetCandidate], dict[str, int]]:
        selected: list[ModerationDatasetCandidate] = []
        shortfalls: dict[str, int] = {}
        by_source: dict[str, list[ModerationDatasetCandidate]] = defaultdict(list)
        for candidate in candidates:
            by_source[candidate.source_bucket].append(candidate)

        negative_class_quotas = self._config.negative_class_quotas()
        selected_negative_counts: Counter[ModerationLabel] = Counter()
        selected_safe = 0

        for source in self._selection_source_order(source_quotas):
            source_quota = source_quotas[source]
            pool = by_source.get(source, [])
            source_selected: list[ModerationDatasetCandidate] = []
            for candidate in pool:
                if len(source_selected) >= source_quota:
                    break
                primary_label = self._candidate_primary_label(candidate)
                if primary_label == ModerationLabel.SAFE:
                    if selected_safe >= self._config.dataset.safe_examples:
                        continue
                    selected_safe += 1
                    source_selected.append(candidate)
                    continue

                target = negative_class_quotas.get(primary_label, 0)
                if selected_negative_counts[primary_label] >= target:
                    continue
                selected_negative_counts[primary_label] += 1
                source_selected.append(candidate)

            selected.extend(source_selected)
            if len(source_selected) < source_quota:
                shortfalls[f"source:{source}"] = source_quota - len(source_selected)

        selected_keys = {(candidate.source_bucket, candidate.source_id) for candidate in selected}
        for candidate in candidates:
            if (candidate.source_bucket, candidate.source_id) in selected_keys:
                continue
            primary_label = self._candidate_primary_label(candidate)
            if primary_label == ModerationLabel.SAFE:
                if selected_safe >= self._config.dataset.safe_examples:
                    continue
                selected_safe += 1
                selected.append(candidate)
                selected_keys.add((candidate.source_bucket, candidate.source_id))
                continue

            target = negative_class_quotas.get(primary_label, 0)
            if selected_negative_counts[primary_label] >= target:
                continue
            selected_negative_counts[primary_label] += 1
            selected.append(candidate)
            selected_keys.add((candidate.source_bucket, candidate.source_id))

        for label, target in negative_class_quotas.items():
            if selected_negative_counts[label] < target:
                shortfalls[f"label:{label.value}"] = target - selected_negative_counts[label]

        if selected_safe < self._config.dataset.safe_examples:
            shortfalls["label:SAFE"] = self._config.dataset.safe_examples - selected_safe

        return selected, shortfalls

    def _selection_source_order(self, source_quotas: dict[str, int]) -> list[str]:
        preferred = [
            "project",
            "project_raw",
            "russian_discord_chat_logs",
            "russian_telegram_chat_logs",
            "russian_dialogues_2",
            "russian_tiny_conversations",
            "hard_toxic_real",
            "hard_nsfw_real",
            "russian_dialogues_safe",
            "russian_dialogsum_safe",
            "russian_literature_safe",
            "russian_kinship_hard_safe",
            "russian_toxic_comments",
            "russian_toxic_dvach",
            "russian_paradetox",
            "russian_react_hate",
            "russian_inappropriate",
            "russian_nsfw_benchmark",
            "russian_nsfw_fiction",
            "russian_toxicity",
            "russian_spam",
            "russian_spam_fork",
            "russian_scam_spam_public",
            "hard_scam_real",
            "phishing_url",
            "discord_phishing_scam",
            "contextual_contrast",
            "manual_synthetic",
            "ai_generated_edge",
        ]
        ordered = [source for source in preferred if source in source_quotas]
        ordered.extend(source for source in source_quotas if source not in ordered)
        return ordered

    def _candidate_primary_label(self, candidate: ModerationDatasetCandidate) -> ModerationLabel:
        return resolve_primary_label(candidate.labels or [candidate.primary_label])

    def _to_training_example(
        self,
        candidate: ModerationDatasetCandidate,
        index: int,
    ) -> TrainingExample:
        primary_label = resolve_primary_label(candidate.labels or [candidate.primary_label])
        source = DatasetSource.PUBLIC_DATASET
        if candidate.source_bucket == "project":
            source = DatasetSource.REAL_MODERATED if primary_label != ModerationLabel.SAFE else DatasetSource.REAL_SAFE
        elif candidate.source_bucket == "manual_synthetic":
            source = DatasetSource.MANUAL_SYNTHETIC
        elif candidate.source_bucket == "ai_generated_edge":
            source = DatasetSource.AI_GENERATED

        return TrainingExample(
            event_id=None,
            message_id=f"{candidate.source_bucket}_{index}_{candidate.source_id}",
            model_text=candidate.text,
            labels=candidate.labels,
            primary_label=primary_label,
            severity=candidate.severity,
            source=source,
            features={},
            rule_matches=[],
            risk_score=0.0 if primary_label == ModerationLabel.SAFE else 50.0,
            decision_action=ModerationAction.IGNORE if primary_label == ModerationLabel.SAFE else ModerationAction.REVIEW,
            feedback_type=FeedbackType.CONFIRMED,
            policy_version="dataset_mix_v1",
            created_at=candidate.created_at,
            metadata={
                "source_bucket": candidate.source_bucket,
                "source_id": candidate.source_id,
                **candidate.metadata,
            },
        )

    def _split_examples(self, examples: list[TrainingExample]) -> dict[str, list[TrainingExample]]:
        by_label: dict[ModerationLabel, list[TrainingExample]] = defaultdict(list)
        for example in examples:
            by_label[example.primary_label].append(example)

        split_quotas = self._config.splits
        splits: dict[str, list[TrainingExample]] = {name: [] for name in split_quotas}
        for label_examples in by_label.values():
            self._random.shuffle(label_examples)
            count = len(label_examples)
            start = 0
            split_counts = self._fractional_counts(split_quotas, count)
            for split_name, split_count in split_counts.items():
                splits[split_name].extend(label_examples[start : start + split_count])
                start += split_count

        for split in splits.values():
            self._random.shuffle(split)
        return splits

    def _fractional_counts(self, ratios: dict[str, float], total: int) -> dict[str, int]:
        raw = {key: value * total for key, value in ratios.items()}
        counts = {key: int(value) for key, value in raw.items()}
        remainder = total - sum(counts.values())
        for key, _ in sorted(raw.items(), key=lambda item: item[1] - int(item[1]), reverse=True):
            if remainder <= 0:
                break
            counts[key] += 1
            remainder -= 1
        return counts

    def _write_exports(self, splits: dict[str, list[TrainingExample]]) -> None:
        output_dir = self._config.dataset.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        row_builder = RuBertDatasetBuilder(self._rubert_config.label_schema)

        def write_split(split_name: str, examples: list[TrainingExample]) -> None:
            path = output_dir / f"{split_name}.jsonl"
            rows = row_builder.build_rows(examples)
            with path.open("w", encoding="utf-8") as file:
                for row in rows:
                    file.write(json.dumps(row, ensure_ascii=False) + "\n")

        # The train/validation/test files are independent.  Parallel writing
        # noticeably reduces the final I/O-bound phase without multiplying the
        # in-memory candidate pool.
        worker_count = min(self._config.dataset.workers, len(splits))
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="dataset-write") as executor:
            futures = [executor.submit(write_split, split_name, examples) for split_name, examples in splits.items()]
            for future in futures:
                future.result()

    def _build_manifest(
        self,
        examples: list[TrainingExample],
        splits: dict[str, list[TrainingExample]],
        source_quotas: dict[str, int],
        shortfalls: dict[str, int],
        load_errors: dict[str, str],
    ) -> dict:
        return {
            "dataset": self._config.dataset.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "target_total": self._config.dataset.total_examples,
            "actual_total": len(examples),
            "source_quotas": source_quotas,
            "shortfalls": shortfalls,
            "load_errors": load_errors,
            "label_counts": Counter(example.primary_label.value for example in examples),
            "source_counts": Counter(str(example.metadata.get("source_bucket")) for example in examples),
            "split_counts": {name: len(items) for name, items in splits.items()},
        }
