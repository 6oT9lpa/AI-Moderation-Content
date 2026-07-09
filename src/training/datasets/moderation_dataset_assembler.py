from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from src.domain.dataset.dataset_source import DatasetSource
from src.domain.dataset.feedback_type import FeedbackType
from src.domain.dto.dataset.training_example import TrainingExample
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_dataset_candidate import ModerationDatasetCandidate
from src.training.datasets.moderation_dataset_mix_config import ModerationDatasetMixConfig
from src.training.datasets.moderation_label_priority import resolve_primary_label
from src.training.datasets.moderation_public_dataset_loaders import (
    HuggingFaceSafeTextLoader,
    HuggingFaceSpamLoader,
    HuggingFaceToxicityLoader,
    ProjectTrainingExampleLoader,
)
from src.training.datasets.synthetic_discord_examples import (
    build_ai_generated_edge_candidates,
    build_manual_synthetic_candidates,
)
from src.training.datasets.training_text_sanitizer import TrainingTextSanitizer
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

    def build(self, *, strict: bool | None = None) -> dict:
        use_strict = self._config.dataset.strict if strict is None else strict
        source_quotas = self._config.source_quotas()
        candidates, load_errors = self._load_candidates(source_quotas)
        candidates = self._quality_filter(candidates)
        selected, shortfalls = self._select_candidates(candidates, source_quotas)

        label_shortfalls = {key: value for key, value in shortfalls.items() if key.startswith("label:")}
        if use_strict and label_shortfalls:
            raise RuntimeError(f"Dataset quotas were not satisfied: {shortfalls}")

        examples = [self._to_training_example(candidate, index) for index, candidate in enumerate(selected)]
        split_examples = self._split_examples(examples)
        self._write_exports(split_examples)
        manifest = self._build_manifest(examples, split_examples, source_quotas, shortfalls, load_errors)
        manifest_path = self._config.dataset.output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest

    def _load_candidates(self, source_quotas: dict[str, int]) -> tuple[list[ModerationDatasetCandidate], dict[str, str]]:
        candidates: list[ModerationDatasetCandidate] = []
        errors: dict[str, str] = {}
        sources = self._config.sources

        if sources.get("project") and sources["project"].enabled:
            path = Path(str(getattr(sources["project"], "path", "data/exports/project_training_examples.jsonl")))
            candidates.extend(ProjectTrainingExampleLoader().load(path))

        if sources.get("russian_toxicity") and sources["russian_toxicity"].enabled:
            spec = sources["russian_toxicity"]
            try:
                candidates.extend(
                    HuggingFaceToxicityLoader().load_textdetox_ru(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_toxicity", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_toxicity"] = str(exc)

        if sources.get("russian_toxic_comments") and sources["russian_toxic_comments"].enabled:
            spec = sources["russian_toxic_comments"]
            try:
                candidates.extend(
                    HuggingFaceToxicityLoader().load_binary_toxicity_dataset(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_toxic_comments", 0) * 3, 100),
                        source_bucket="russian_toxic_comments",
                    )
                )
            except Exception as exc:
                errors["russian_toxic_comments"] = str(exc)

        if sources.get("russian_inappropriate") and sources["russian_inappropriate"].enabled:
            spec = sources["russian_inappropriate"]
            try:
                candidates.extend(
                    HuggingFaceToxicityLoader().load_inappropriateness_dataset(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
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

        if sources.get("russian_toxic_dvach") and sources["russian_toxic_dvach"].enabled:
            spec = sources["russian_toxic_dvach"]
            try:
                candidates.extend(
                    HuggingFaceToxicityLoader().load_toxic_dvach_dataset(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_toxic_dvach", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_toxic_dvach"] = str(exc)

        if sources.get("russian_dialogues_safe") and sources["russian_dialogues_safe"].enabled:
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
            spec = sources["russian_literature_safe"]
            try:
                candidates.extend(
                    HuggingFaceSafeTextLoader().load_literature_safe(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_literature_safe", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_literature_safe"] = str(exc)

        if sources.get("russian_spam") and sources["russian_spam"].enabled:
            spec = sources["russian_spam"]
            try:
                candidates.extend(
                    HuggingFaceSpamLoader().load_spam_dataset(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_spam", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_spam"] = str(exc)

        if sources.get("russian_spam_fork") and sources["russian_spam_fork"].enabled:
            spec = sources["russian_spam_fork"]
            try:
                candidates.extend(
                    HuggingFaceSpamLoader().load_spam_dataset(
                        str(getattr(spec, "dataset_id")),
                        str(getattr(spec, "split")),
                        limit=max(source_quotas.get("russian_spam_fork", 0) * 3, 100),
                    )
                )
            except Exception as exc:
                errors["russian_spam_fork"] = str(exc)

        if sources.get("russian_scam_spam_public") and sources["russian_scam_spam_public"].enabled:
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

        if sources.get("manual_synthetic") and sources["manual_synthetic"].enabled:
            manual_templates = build_manual_synthetic_candidates()
            candidates.extend(
                self._expand_templates(
                    manual_templates,
                    max(source_quotas["manual_synthetic"], self._config.dataset.negative_examples),
                )
            )
            candidates.extend(self._expand_label_templates(manual_templates, self._config.negative_class_quotas()))

        if sources.get("ai_generated_edge") and sources["ai_generated_edge"].enabled:
            edge_templates = build_ai_generated_edge_candidates()
            candidates.extend(
                self._expand_templates(
                    edge_templates,
                    max(source_quotas["ai_generated_edge"], self._config.dataset.negative_examples // 2),
                )
            )
            candidates.extend(self._expand_label_templates(edge_templates, self._config.negative_class_quotas()))

        self._random.shuffle(candidates)
        return candidates, errors

    def _expand_templates(
        self,
        templates: list[ModerationDatasetCandidate],
        target: int,
    ) -> list[ModerationDatasetCandidate]:
        if not templates:
            return []

        expanded: list[ModerationDatasetCandidate] = []
        index = 0
        while len(expanded) < target:
            template = templates[index % len(templates)]
            expanded.append(
                template.model_copy(
                    update={
                        "source_id": f"{template.source_id}_variant_{index}",
                        "text": f"{template.text} #{index % 97}",
                    }
                )
            )
            index += 1

        return expanded

    def _expand_label_templates(
        self,
        templates: list[ModerationDatasetCandidate],
        targets: dict[ModerationLabel, int],
    ) -> list[ModerationDatasetCandidate]:
        expanded: list[ModerationDatasetCandidate] = []
        by_label: dict[ModerationLabel, list[ModerationDatasetCandidate]] = defaultdict(list)
        for template in templates:
            by_label[template.primary_label].append(template)

        for label, target in targets.items():
            pool = by_label.get(label, [])
            if not pool:
                continue
            for index in range(target):
                template = pool[index % len(pool)]
                expanded.append(
                    template.model_copy(
                        update={
                            "source_id": f"{template.source_id}_label_backfill_{index}",
                            "text": f"{template.text} #{index % 997}",
                        }
                    )
                )

        return expanded

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
            if self._config.quality.deduplicate_by_text and model_text in seen:
                continue
            seen.add(model_text)
            filtered.append(candidate.model_copy(update={"text": model_text}))
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
            "russian_dialogues_safe",
            "russian_literature_safe",
            "russian_toxic_comments",
            "russian_toxic_dvach",
            "russian_inappropriate",
            "russian_nsfw_benchmark",
            "russian_toxicity",
            "russian_spam",
            "russian_spam_fork",
            "russian_scam_spam_public",
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

        for split_name, examples in splits.items():
            path = output_dir / f"{split_name}.jsonl"
            rows = row_builder.build_rows(examples)
            with path.open("w", encoding="utf-8") as file:
                for row in rows:
                    file.write(json.dumps(row, ensure_ascii=False) + "\n")

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
