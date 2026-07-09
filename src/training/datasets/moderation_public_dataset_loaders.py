from __future__ import annotations

import json
import re
import gzip
from csv import DictReader
from pathlib import Path
from typing import Any

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_dataset_candidate import ModerationDatasetCandidate
from src.training.datasets.moderation_export_relabeler import ModerationExportRelabeler
from src.training.datasets.moderation_label_priority import resolve_primary_label
from src.training.datasets.training_text_sanitizer import TrainingTextSanitizer


class ProjectTrainingExampleLoader:
    def load(self, path: Path) -> list[ModerationDatasetCandidate]:
        if not path.exists():
            return []

        candidates: list[ModerationDatasetCandidate] = []
        with path.open("r", encoding="utf-8") as file:
            for index, line in enumerate(file):
                if not line.strip():
                    continue
                row = json.loads(line)
                text = str(row.get("model_text") or row.get("text") or "")
                labels = [ModerationLabel(label) for label in row.get("labels", [])]
                fallback = ModerationLabel(row.get("primary_label", labels[0].value if labels else "SAFE"))
                primary_label = resolve_primary_label(labels or [fallback])
                candidates.append(
                    ModerationDatasetCandidate(
                        text=text,
                        labels=labels or [primary_label],
                        primary_label=primary_label,
                        source_bucket="project",
                        source_id=str(row.get("message_id") or row.get("event_id") or f"project_{index}"),
                        severity=int(row.get("severity", 0 if primary_label == ModerationLabel.SAFE else 2)),
                        metadata={"raw_source": "project_jsonl", "row": row},
                    )
                )

        return candidates


class DiscordRawMessageLoader:
    def load(self, path: Path, *, limit: int) -> list[ModerationDatasetCandidate]:
        if not path.exists():
            return []

        relabeler = ModerationExportRelabeler()
        sanitizer = TrainingTextSanitizer()
        candidates: list[ModerationDatasetCandidate] = []
        with path.open("r", encoding="utf-8") as file:
            for index, line in enumerate(file):
                if len(candidates) >= limit:
                    break
                if not line.strip():
                    continue
                row = json.loads(line)
                text = str(row.get("content") or "").strip()
                if not text:
                    continue
                model_text = sanitizer.sanitize(text)
                relabeled = relabeler.relabel_row(
                    {
                        "model_text": model_text,
                        "labels": [ModerationLabel.SAFE.value],
                        "primary_label": ModerationLabel.SAFE.value,
                        "severity": 0,
                    }
                )
                labels = [ModerationLabel(label) for label in relabeled.get("labels", [])]
                primary_label = ModerationLabel(str(relabeled.get("primary_label") or ModerationLabel.SAFE.value))
                candidates.append(
                    ModerationDatasetCandidate(
                        text=model_text,
                        labels=labels or [primary_label],
                        primary_label=primary_label,
                        source_bucket="project_raw",
                        source_id=str(row.get("message_id") or f"discord_raw_{index}"),
                        severity=int(relabeled.get("severity") or 0),
                        metadata={
                            "raw_source": "discord_raw_jsonl",
                            "labeler": "moderation_export_relabeler_v1",
                            "guild_id_hash": row.get("guild_id_hash"),
                            "channel_id_hash": row.get("channel_id_hash"),
                            "user_id_hash": row.get("user_id_hash"),
                            "created_at": row.get("created_at"),
                        },
                    )
                )

        return candidates


class LocalCuratedDatasetLoader:
    """Read downloaded Russian corpora without a live Hugging Face request."""

    def load_binary_jsonl(self, path: Path, *, source_bucket: str, limit: int) -> list[ModerationDatasetCandidate]:
        if not path.exists():
            return []
        candidates: list[ModerationDatasetCandidate] = []
        with path.open("r", encoding="utf-8") as file:
            for index, line in enumerate(file):
                if len(candidates) >= limit:
                    break
                if line.strip():
                    row = json.loads(line)
                    candidates.extend(self._to_candidate(str(row.get("text") or ""), row.get("label"), source_bucket, f"{path.name}:{index}", ModerationLabel.TOXIC))
        return candidates

    def load_binary_csv(self, path: Path, *, source_bucket: str, limit: int) -> list[ModerationDatasetCandidate]:
        if not path.exists():
            return []
        candidates: list[ModerationDatasetCandidate] = []
        with path.open("r", encoding="utf-8", newline="") as file:
            for index, row in enumerate(DictReader(file)):
                if len(candidates) >= limit:
                    break
                candidates.extend(self._to_candidate(str(row.get("comment") or ""), row.get("toxic"), source_bucket, f"{path.name}:{index}", ModerationLabel.TOXIC))
        return candidates

    def load_spam_parquet(self, path: Path, *, source_bucket: str, limit: int) -> list[ModerationDatasetCandidate]:
        return self.load_parquet_binary(
            path,
            source_bucket=source_bucket,
            limit=limit,
            text_keys=("message", "text"),
            label_key="label",
            positive_label=ModerationLabel.SPAM,
        )

    def load_parquet_binary(
        self,
        path: Path,
        *,
        source_bucket: str,
        limit: int,
        text_keys: tuple[str, ...] = ("text",),
        label_key: str,
        positive_label: ModerationLabel,
        positive_values: set[str] | None = None,
    ) -> list[ModerationDatasetCandidate]:
        if not path.exists():
            return []
        try:
            from pyarrow.parquet import ParquetFile
        except ImportError as exc:
            raise RuntimeError("Install pyarrow to read the local Russian spam corpus.") from exc

        candidates: list[ModerationDatasetCandidate] = []
        columns = list(dict.fromkeys([*text_keys, label_key]))
        for batch in ParquetFile(path).iter_batches(batch_size=8192, columns=columns):
            for index, row in enumerate(batch.to_pylist()):
                if len(candidates) >= limit:
                    return candidates
                text = next((str(row.get(key) or "") for key in text_keys if row.get(key)), "")
                candidates.extend(self._to_candidate(
                    text,
                    row.get(label_key),
                    source_bucket,
                    f"{path.name}:{len(candidates)}:{index}",
                    positive_label,
                    positive_values=positive_values,
                ))
        return candidates

    def load_react_hate(self, paths: list[Path], *, source_bucket: str, limit: int) -> list[ModerationDatasetCandidate]:
        candidates: list[ModerationDatasetCandidate] = []
        for path in paths:
            if len(candidates) >= limit:
                break
            candidates.extend(self.load_parquet_binary(
                path,
                source_bucket=source_bucket,
                limit=limit - len(candidates),
                text_keys=("text",),
                label_key="majority_polarity",
                positive_label=ModerationLabel.HATE,
                positive_values={"hateful"},
            ))
        return candidates

    def load_inappropriate_csv(self, path: Path, *, source_bucket: str, limit: int, toxic_threshold: float, safe_threshold: float) -> list[ModerationDatasetCandidate]:
        if not path.exists():
            return []
        candidates: list[ModerationDatasetCandidate] = []
        with path.open("r", encoding="utf-8", newline="") as file:
            for index, row in enumerate(DictReader(file)):
                if len(candidates) >= limit:
                    break
                try:
                    score = float(row.get("inappropriate") or 0)
                except ValueError:
                    continue
                if score >= toxic_threshold:
                    raw_label = "true"
                elif score <= safe_threshold:
                    raw_label = "false"
                else:
                    continue
                candidates.extend(self._to_candidate(str(row.get("text") or ""), raw_label, source_bucket, f"{path.name}:{index}", ModerationLabel.TOXIC))
        return candidates

    def load_nsfw_parquet(self, path: Path, *, source_bucket: str, limit: int) -> list[ModerationDatasetCandidate]:
        if not path.exists():
            return []
        try:
            from pyarrow.parquet import ParquetFile
        except ImportError as exc:
            raise RuntimeError("Install pyarrow to read downloaded datasets.") from exc
        candidates: list[ModerationDatasetCandidate] = []
        for batch in ParquetFile(path).iter_batches(batch_size=8192, columns=["text"]):
            for index, row in enumerate(batch.to_pylist()):
                if len(candidates) >= limit:
                    return candidates
                candidates.extend(self._to_candidate(str(row.get("text") or ""), "true", source_bucket, f"{path.name}:{len(candidates)}:{index}", ModerationLabel.NSFW))
        return candidates

    def load_dialogue_safe(self, path: Path, *, source_bucket: str, limit: int) -> list[ModerationDatasetCandidate]:
        return self.load_parquet_safe(path, source_bucket=source_bucket, limit=limit, text_key="dialogue")

    def load_chat_log_parquet(self, path: Path, *, source_bucket: str, limit: int) -> list[ModerationDatasetCandidate]:
        if not path.exists():
            return []
        try:
            from pyarrow.parquet import ParquetFile
        except ImportError as exc:
            raise RuntimeError("Install pyarrow to read downloaded datasets.") from exc

        candidates: list[ModerationDatasetCandidate] = []
        for batch in ParquetFile(path).iter_batches(batch_size=4096, columns=["message", "semantic_score"]):
            for index, row in enumerate(batch.to_pylist()):
                if len(candidates) >= limit:
                    return candidates
                built = self._to_candidate(
                    str(row.get("message") or ""),
                    "false",
                    source_bucket,
                    f"{path.name}:{len(candidates)}:{index}",
                    ModerationLabel.TOXIC,
                )
                if built:
                    candidates.append(built[0].model_copy(update={
                        "metadata": {
                            **built[0].metadata,
                            "semantic_score": row.get("semantic_score"),
                            "raw_source": "downloaded_chat_log",
                        }
                    }))
        return candidates

    def load_dialogues_gzip(self, path: Path, *, source_bucket: str, limit: int) -> list[ModerationDatasetCandidate]:
        if not path.exists():
            return []
        candidates: list[ModerationDatasetCandidate] = []
        with gzip.open(path, "rt", encoding="utf-8") as file:
            for dialogue_index, line in enumerate(file):
                if len(candidates) >= limit:
                    break
                if not line.strip():
                    continue
                row = json.loads(line)
                turns = row.get("sample") or row.get("dialogue") or row.get("messages") or []
                if not isinstance(turns, list):
                    continue
                for turn_index, turn in enumerate(turns):
                    if len(candidates) >= limit:
                        break
                    built = self._to_candidate(
                        str(turn or ""),
                        "false",
                        source_bucket,
                        f"{path.name}:{dialogue_index}:{turn_index}",
                        ModerationLabel.TOXIC,
                    )
                    if built:
                        candidates.append(built[0].model_copy(update={
                            "metadata": {**built[0].metadata, "raw_source": "downloaded_dialogue_turn"}
                        }))
        return candidates

    def load_parquet_safe(self, path: Path, *, source_bucket: str, limit: int, text_key: str) -> list[ModerationDatasetCandidate]:
        if not path.exists():
            return []
        try:
            from pyarrow.parquet import ParquetFile
        except ImportError as exc:
            raise RuntimeError("Install pyarrow to read downloaded datasets.") from exc
        candidates: list[ModerationDatasetCandidate] = []
        relabeler = ModerationExportRelabeler()
        sanitizer = TrainingTextSanitizer()
        for batch in ParquetFile(path).iter_batches(batch_size=8192, columns=[text_key]):
            for index, row in enumerate(batch.to_pylist()):
                if len(candidates) >= limit:
                    return candidates
                text = sanitizer.sanitize(str(row.get(text_key) or ""))[:512].strip()
                relabeled = relabeler.relabel_row({"model_text": text, "labels": ["SAFE"], "primary_label": "SAFE"})
                if text and relabeled.get("primary_label") == ModerationLabel.SAFE.value:
                    candidates.append(ModerationDatasetCandidate(
                        text=text, labels=[ModerationLabel.SAFE], primary_label=ModerationLabel.SAFE,
                        source_bucket=source_bucket, source_id=f"{path.name}:{len(candidates)}:{index}", severity=0,
                        metadata={"raw_source": "local_download"},
                    ))
        return candidates

    def load_literature_safe(self, path: Path, *, source_bucket: str, limit: int) -> list[ModerationDatasetCandidate]:
        if not path.exists():
            return []
        relabeler = ModerationExportRelabeler()
        sanitizer = TrainingTextSanitizer()
        candidates: list[ModerationDatasetCandidate] = []
        with path.open("r", encoding="utf-8") as file:
            for index, line in enumerate(file):
                if len(candidates) >= limit:
                    break
                if not line.strip():
                    continue
                row = json.loads(line)
                text = sanitizer.sanitize(str(row.get("text") or ""))[:512].strip()
                relabeled = relabeler.relabel_row({"model_text": text, "labels": ["SAFE"], "primary_label": "SAFE"})
                if text and relabeled.get("primary_label") == ModerationLabel.SAFE.value:
                    candidates.append(ModerationDatasetCandidate(
                        text=text, labels=[ModerationLabel.SAFE], primary_label=ModerationLabel.SAFE,
                        source_bucket=source_bucket, source_id=f"{path.name}:{index}", severity=0,
                        metadata={"raw_source": "local_russian_literature", "author": row.get("author")},
                    ))
        return candidates

    def _to_candidate(
        self,
        text: str,
        raw_label: Any,
        source_bucket: str,
        source_id: str,
        positive_label: ModerationLabel,
        *,
        positive_values: set[str] | None = None,
    ) -> list[ModerationDatasetCandidate]:
        if not text.strip():
            return []
        model_text = TrainingTextSanitizer().sanitize(text)[:512].strip()
        if not model_text:
            return []
        positive = str(raw_label).strip().casefold() in (positive_values or {"1", "1.0", "true", "spam", "toxic"})
        base_labels = [positive_label] if positive else [ModerationLabel.SAFE]
        relabeled = ModerationExportRelabeler().relabel_row({
            "model_text": model_text,
            "labels": [label.value for label in base_labels],
            "primary_label": resolve_primary_label(base_labels).value,
        })
        labels = [ModerationLabel(label) for label in relabeled.get("labels", [])]
        primary = ModerationLabel(str(relabeled.get("primary_label") or "SAFE"))
        return [ModerationDatasetCandidate(
            text=model_text, labels=labels or [primary], primary_label=primary, source_bucket=source_bucket,
            source_id=source_id, severity=int(relabeled.get("severity") or 0),
            metadata={"raw_source": "local_download", "raw_label": raw_label},
        )]


class CachedTranslatedDatasetLoader:
    def load(
        self,
        path: Path,
        *,
        source_bucket: str,
        limit: int,
    ) -> list[ModerationDatasetCandidate]:
        if not path.exists():
            return []

        candidates: list[ModerationDatasetCandidate] = []
        with path.open("r", encoding="utf-8") as file:
            for index, line in enumerate(file):
                if len(candidates) >= limit:
                    break
                if not line.strip():
                    continue
                row = json.loads(line)
                text = str(row.get("model_text") or row.get("text") or "").strip()
                if not text:
                    continue
                labels = [ModerationLabel(label) for label in row.get("labels", [])]
                primary_label = resolve_primary_label(labels or [ModerationLabel(str(row.get("primary_label", "SPAM")))])
                if primary_label == ModerationLabel.SAFE:
                    continue
                candidates.append(
                    ModerationDatasetCandidate(
                        text=text,
                        labels=labels or [primary_label],
                        primary_label=primary_label,
                        source_bucket=source_bucket,
                        source_id=str(row.get("source_id") or row.get("message_id") or f"{source_bucket}_{index}"),
                        severity=int(row.get("severity", 3)),
                        metadata={
                            "raw_source": "translated_cache_jsonl",
                            "translation_source": row.get("translation_source"),
                            "original_language": row.get("original_language"),
                            "row": row,
                        },
                    )
                )

        return candidates


class HuggingFaceToxicityLoader:
    def load_textdetox_ru(self, dataset_id: str, split: str, *, limit: int) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        candidates: list[ModerationDatasetCandidate] = []

        for index, row in enumerate(dataset):
            if len(candidates) >= limit:
                break
            text = self._extract_text(row)
            if not text:
                continue
            toxic = bool(row.get("toxic", False))
            label = ModerationLabel.TOXIC if toxic else ModerationLabel.SAFE
            candidates.append(
                ModerationDatasetCandidate(
                    text=text,
                    labels=[label],
                    primary_label=label,
                    source_bucket="russian_toxicity",
                    source_id=f"{dataset_id}:{split}:{index}",
                    severity=3 if toxic else 0,
                    metadata={
                        "dataset_id": dataset_id,
                        "split": split,
                        "license_check_required": True,
                        "raw_label": row.get("toxic"),
                    },
                )
            )

        return candidates

    def _extract_text(self, row: dict[str, Any]) -> str:
        for key in ("text", "comment", "message", "content"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                return value

        return ""

    def load_binary_toxicity_dataset(
        self,
        dataset_id: str,
        split: str,
        *,
        limit: int,
        source_bucket: str,
        text_keys: tuple[str, ...] = ("text", "comment", "message", "content"),
        label_keys: tuple[str, ...] = ("label", "toxic", "toxicity", "target"),
        positive_label_values: tuple[object, ...] = (1, "1", True, "true", "toxic"),
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        positives = {str(value).casefold() for value in positive_label_values}
        candidates: list[ModerationDatasetCandidate] = []

        for index, row in enumerate(dataset):
            if len(candidates) >= limit:
                break
            text = self._extract_text_by_keys(row, text_keys)
            if not text:
                continue
            raw_label = self._extract_first(row, label_keys)
            label = ModerationLabel.TOXIC if str(raw_label).casefold() in positives else ModerationLabel.SAFE
            candidates.append(
                ModerationDatasetCandidate(
                    text=text,
                    labels=[label],
                    primary_label=label,
                    source_bucket=source_bucket,
                    source_id=f"{dataset_id}:{split}:{index}",
                    severity=3 if label == ModerationLabel.TOXIC else 0,
                    metadata={
                        "dataset_id": dataset_id,
                        "split": split,
                        "license_check_required": True,
                        "raw_label": raw_label,
                    },
                )
            )

        return candidates

    def load_inappropriateness_dataset(
        self,
        dataset_id: str,
        split: str,
        *,
        limit: int,
        toxic_threshold: float = 0.75,
        safe_threshold: float = 0.25,
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        candidates: list[ModerationDatasetCandidate] = []

        for index, row in enumerate(dataset):
            if len(candidates) >= limit:
                break
            text = self._extract_text_by_keys(row, ("text", "comment", "message", "content"))
            if not text:
                continue
            score = self._to_float(row.get("inappropriate"))
            if score is None:
                continue
            if score >= toxic_threshold:
                label = ModerationLabel.TOXIC
            elif score <= safe_threshold:
                label = ModerationLabel.SAFE
            else:
                continue
            candidates.append(
                ModerationDatasetCandidate(
                    text=text,
                    labels=[label],
                    primary_label=label,
                    source_bucket="russian_inappropriate",
                    source_id=f"{dataset_id}:{split}:{index}",
                    severity=3 if label == ModerationLabel.TOXIC else 0,
                    metadata={
                        "dataset_id": dataset_id,
                        "split": split,
                        "license_check_required": True,
                        "raw_label": score,
                    },
                )
            )

        return candidates

    def load_redmadrobot_nsfw_benchmark(
        self,
        dataset_id: str,
        split: str,
        *,
        limit: int,
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        candidates: list[ModerationDatasetCandidate] = []

        for index, row in enumerate(dataset):
            if len(candidates) >= limit:
                break
            if str(row.get("language", "")).casefold() != "ru":
                continue
            if str(row.get("category", "")).casefold() != "erotic":
                continue

            text = self._extract_text_by_keys(row, ("text", "prompt", "message", "content"))
            if not text:
                continue
            raw_label = row.get("label")
            label = ModerationLabel.NSFW if str(raw_label) == "1" else ModerationLabel.SAFE
            candidates.append(
                ModerationDatasetCandidate(
                    text=text,
                    labels=[label],
                    primary_label=label,
                    source_bucket="russian_nsfw_benchmark",
                    source_id=f"{dataset_id}:{split}:{index}",
                    severity=4 if label == ModerationLabel.NSFW else 0,
                    metadata={
                        "dataset_id": dataset_id,
                        "split": split,
                        "license_check_required": True,
                        "raw_label": raw_label,
                        "category": row.get("category"),
                        "type": row.get("type"),
                    },
                )
            )

        return candidates

    def load_nsfw_fiction_dataset(
        self,
        dataset_id: str,
        split: str,
        *,
        limit: int,
        source_bucket: str,
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        sanitizer = TrainingTextSanitizer()
        candidates: list[ModerationDatasetCandidate] = []
        blocked_tags = ("underage", "зооф", "несовершеннолет", "rape", "изнас", "школь")

        for index, row in enumerate(dataset):
            if len(candidates) >= limit:
                break
            tags = str(row.get("tags") or "").casefold()
            if any(tag in tags for tag in blocked_tags):
                continue
            text = self._extract_text_by_keys(row, ("text", "content", "message"))
            if not text:
                continue
            model_text = sanitizer.sanitize(text)
            if len(model_text) > 512:
                model_text = model_text[:512].strip()
            candidates.append(
                ModerationDatasetCandidate(
                    text=model_text,
                    labels=[ModerationLabel.NSFW],
                    primary_label=ModerationLabel.NSFW,
                    source_bucket=source_bucket,
                    source_id=f"{dataset_id}:{split}:{index}",
                    severity=4,
                    metadata={
                        "dataset_id": dataset_id,
                        "split": split,
                        "license_check_required": True,
                        "safety_filter": "blocked_underage_zoo_nonconsensual_tags",
                        "raw_tags": row.get("tags"),
                    },
                )
            )

        return candidates

    def load_toxic_dvach_dataset(
        self,
        dataset_id: str,
        split: str,
        *,
        limit: int,
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        relabeler = ModerationExportRelabeler()
        sanitizer = TrainingTextSanitizer()
        candidates: list[ModerationDatasetCandidate] = []

        for index, row in enumerate(dataset):
            if len(candidates) >= limit:
                break
            text = self._extract_text_by_keys(row, ("comment", "text", "message", "content"))
            if not text:
                continue
            model_text = sanitizer.sanitize(text)
            raw_label = row.get("toxic")
            base_label = ModerationLabel.TOXIC if self._to_float(raw_label) and self._to_float(raw_label) >= 0.5 else ModerationLabel.SAFE
            relabeled = relabeler.relabel_row(
                {
                    "model_text": model_text,
                    "labels": [base_label.value],
                    "primary_label": base_label.value,
                    "severity": 3 if base_label == ModerationLabel.TOXIC else 0,
                }
            )
            labels = [ModerationLabel(label) for label in relabeled.get("labels", [])]
            primary_label = ModerationLabel(str(relabeled.get("primary_label") or base_label.value))
            candidates.append(
                ModerationDatasetCandidate(
                    text=model_text,
                    labels=labels or [primary_label],
                    primary_label=primary_label,
                    source_bucket="russian_toxic_dvach",
                    source_id=f"{dataset_id}:{split}:{index}",
                    severity=int(relabeled.get("severity") or (3 if primary_label != ModerationLabel.SAFE else 0)),
                    metadata={
                        "dataset_id": dataset_id,
                        "split": split,
                        "license_check_required": True,
                        "raw_label": raw_label,
                        "safe_filter": "moderation_export_relabeler_v1",
                    },
                )
            )

        return candidates

    def load_paradetox_ru_dataset(
        self,
        dataset_id: str,
        split: str,
        *,
        limit: int,
        source_bucket: str,
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        relabeler = ModerationExportRelabeler()
        sanitizer = TrainingTextSanitizer()
        candidates: list[ModerationDatasetCandidate] = []

        for index, row in enumerate(dataset):
            if len(candidates) >= limit:
                break
            for variant, text, base_label in (
                ("toxic", str(row.get("toxic_sentence") or "").strip(), ModerationLabel.TOXIC),
                ("neutral", str(row.get("neutral_sentence") or "").strip(), ModerationLabel.SAFE),
            ):
                if len(candidates) >= limit:
                    break
                if not text:
                    continue
                model_text = sanitizer.sanitize(text)
                relabeled = relabeler.relabel_row(
                    {
                        "model_text": model_text,
                        "labels": [base_label.value],
                        "primary_label": base_label.value,
                        "severity": 3 if base_label == ModerationLabel.TOXIC else 0,
                    }
                )
                labels = [ModerationLabel(label) for label in relabeled.get("labels", [])]
                primary_label = ModerationLabel(str(relabeled.get("primary_label") or base_label.value))
                candidates.append(
                    ModerationDatasetCandidate(
                        text=model_text,
                        labels=labels or [primary_label],
                        primary_label=primary_label,
                        source_bucket=source_bucket,
                        source_id=f"{dataset_id}:{split}:{index}:{variant}",
                        severity=int(relabeled.get("severity") or (3 if primary_label != ModerationLabel.SAFE else 0)),
                        metadata={
                            "dataset_id": dataset_id,
                            "split": split,
                            "license_check_required": True,
                            "labeler": "moderation_export_relabeler_v1",
                            "variant": variant,
                        },
                    )
                )

        return candidates

    def load_react_hate_dataset(
        self,
        dataset_id: str,
        splits: tuple[str, ...],
        *,
        limit: int,
        source_bucket: str,
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        relabeler = ModerationExportRelabeler()
        sanitizer = TrainingTextSanitizer()
        candidates: list[ModerationDatasetCandidate] = []

        for split in splits:
            dataset = load_dataset(dataset_id, split=split, streaming=True)
            for index, row in enumerate(dataset):
                if len(candidates) >= limit:
                    return candidates
                text = self._extract_text_by_keys(row, ("text", "comment", "message", "content"))
                if not text:
                    continue
                polarity = str(row.get("majority_polarity") or row.get("orig_polarity") or "").casefold()
                profanity = str(row.get("majority_profanity") or row.get("orig_profanity") or "").casefold()
                if polarity not in {"hateful", "neutral"}:
                    continue

                base_label = ModerationLabel.HATE if polarity == "hateful" else ModerationLabel.SAFE
                base_labels = [base_label]
                if base_label == ModerationLabel.HATE and profanity == "profane":
                    base_labels.append(ModerationLabel.TOXIC)

                model_text = sanitizer.sanitize(text)
                relabeled = relabeler.relabel_row(
                    {
                        "model_text": model_text,
                        "labels": [label.value for label in base_labels],
                        "primary_label": resolve_primary_label(base_labels).value,
                        "severity": 5 if base_label == ModerationLabel.HATE else 0,
                    }
                )
                labels = [ModerationLabel(label) for label in relabeled.get("labels", [])]
                primary_label = ModerationLabel(str(relabeled.get("primary_label") or base_label.value))
                candidates.append(
                    ModerationDatasetCandidate(
                        text=model_text,
                        labels=labels or [primary_label],
                        primary_label=primary_label,
                        source_bucket=source_bucket,
                        source_id=f"{dataset_id}:{split}:{index}",
                        severity=int(relabeled.get("severity") or (5 if primary_label != ModerationLabel.SAFE else 0)),
                        metadata={
                            "dataset_id": dataset_id,
                            "split": split,
                            "license_check_required": True,
                            "labeler": "moderation_export_relabeler_v1",
                            "raw_polarity": polarity,
                            "raw_profanity": profanity,
                        },
                    )
                )

        return candidates

    def _extract_text_by_keys(self, row: dict[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return ""

    def _extract_first(self, row: dict[str, Any], keys: tuple[str, ...]) -> object:
        for key in keys:
            if key in row:
                return row[key]
        return None

    def _to_float(self, value: object) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class HuggingFaceSafeTextLoader:
    def __init__(self) -> None:
        self._relabeler = ModerationExportRelabeler()
        self._sanitizer = TrainingTextSanitizer()
        self._kinship_terms = (
            "мама",
            "маме",
            "маму",
            "мамой",
            "мать",
            "матери",
            "отец",
            "отца",
            "папа",
            "папе",
            "папу",
            "родител",
            "сестра",
            "сестре",
            "сестру",
            "сестрен",
            "брат",
            "брата",
            "брату",
            "дочь",
            "дочк",
            "сын",
            "сына",
            "сыну",
            "бабушк",
            "дедушк",
        )
        self._home_context_terms = (
            "дом",
            "дома",
            "гости",
            "гостях",
            "приход",
            "встреч",
            "ужин",
            "обед",
            "чай",
            "учеб",
            "проект",
            "урок",
            "книга",
            "родительск",
            "семейн",
        )
        self._hard_safe_block_terms = (
            "били",
            "кнут",
            "смерт",
            "убий",
            "убил",
            "войн",
            "сеч",
            "кров",
            "рабств",
            "плен",
            "насил",
            "интим",
            "эрот",
            "секс",
            "шлюх",
        )

    def load_dialogues_relabelled(
        self,
        dataset_id: str,
        split: str,
        *,
        limit: int,
        max_rows: int | None = None,
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        candidates: list[ModerationDatasetCandidate] = []
        scan_limit = max_rows or max(limit * 50, 1000)

        for index, row in enumerate(dataset):
            if len(candidates) >= limit or index >= scan_limit:
                break

            question = str(row.get("question") or "").strip()
            answer = str(row.get("answer") or "").strip()
            if not question or not answer:
                continue

            text = f"{question}\n{answer}"
            candidate = self._build_relabelled_candidate(
                text,
                source_bucket="russian_dialogues_safe",
                source_id=f"{dataset_id}:{split}:{index}",
                metadata={
                    "dataset_id": dataset_id,
                    "split": split,
                    "license": "mit",
                    "labeler": "moderation_export_relabeler_v1",
                    "raw_relevance": row.get("relevance"),
                },
            )
            if candidate:
                candidates.append(candidate)

        return candidates

    def _build_relabelled_candidate(
        self,
        text: str,
        *,
        source_bucket: str,
        source_id: str,
        metadata: dict[str, Any],
    ) -> ModerationDatasetCandidate | None:
        model_text = self._sanitizer.sanitize(text)
        if len(model_text) < 16:
            return None

        relabeled = self._relabeler.relabel_row(
            {
                "model_text": model_text,
                "labels": [ModerationLabel.SAFE.value],
                "primary_label": ModerationLabel.SAFE.value,
                "severity": 0,
            }
        )
        labels = [ModerationLabel(label) for label in relabeled.get("labels", [])]
        primary_label = ModerationLabel(str(relabeled.get("primary_label") or ModerationLabel.SAFE.value))
        return ModerationDatasetCandidate(
            text=model_text,
            labels=labels or [primary_label],
            primary_label=primary_label,
            source_bucket=source_bucket,
            source_id=source_id,
            severity=int(relabeled.get("severity") or 0),
            metadata=metadata,
        )

    def load_literature_safe(
        self,
        dataset_id: str,
        split: str,
        *,
        limit: int,
        max_rows: int | None = None,
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        candidates: list[ModerationDatasetCandidate] = []
        scan_limit = max_rows or max(limit * 20, 500)

        for index, row in enumerate(dataset):
            if len(candidates) >= limit or index >= scan_limit:
                break

            text = str(row.get("text") or "").strip()
            if not text:
                continue

            for chunk_index, chunk in enumerate(self._chunk_text(text)):
                if len(candidates) >= limit:
                    break
                candidate = self._build_safe_candidate(
                    chunk,
                    source_bucket="russian_literature_safe",
                    source_id=f"{dataset_id}:{split}:{index}:{chunk_index}",
                    metadata={
                        "dataset_id": dataset_id,
                        "split": split,
                        "license_check_required": True,
                        "safe_filter": "moderation_export_relabeler_v1",
                        "raw_type": row.get("type"),
                        "raw_author": row.get("author"),
                    },
                )
                if candidate:
                    candidates.append(candidate)

        return candidates

    def load_dialogsum_safe(
        self,
        dataset_id: str,
        split: str,
        *,
        limit: int,
        max_rows: int | None = None,
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        candidates: list[ModerationDatasetCandidate] = []
        scan_limit = max_rows or max(limit * 5, 1000)

        for index, row in enumerate(dataset):
            if len(candidates) >= limit or index >= scan_limit:
                break
            text = str(row.get("dialogue") or "").strip()
            if not text:
                continue
            candidate = self._build_safe_candidate(
                text,
                source_bucket="russian_dialogsum_safe",
                source_id=f"{dataset_id}:{split}:{index}",
                metadata={
                    "dataset_id": dataset_id,
                    "split": split,
                    "license_check_required": True,
                    "safe_filter": "moderation_export_relabeler_v1",
                    "topic": row.get("topic"),
                },
            )
            if candidate:
                candidates.append(candidate)

        return candidates

    def load_kinship_hard_safe(
        self,
        datasets: list[dict[str, Any]],
        *,
        limit: int,
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        candidates: list[ModerationDatasetCandidate] = []

        for dataset_spec in datasets:
            dataset_id = str(dataset_spec.get("dataset_id") or "")
            split = str(dataset_spec.get("split") or "train")
            kind = str(dataset_spec.get("kind") or "generic")
            if not dataset_id:
                continue

            try:
                dataset = load_dataset(dataset_id, split=split, streaming=True)
            except Exception:
                continue
            accepted_for_dataset = 0
            remaining = limit - len(candidates)
            scan_limit = max(remaining * 80, 2000)

            for index, row in enumerate(dataset):
                if len(candidates) >= limit or accepted_for_dataset >= remaining or index >= scan_limit:
                    break

                for text_index, text in enumerate(self._extract_candidate_texts(row, kind=kind)):
                    if len(candidates) >= limit or accepted_for_dataset >= remaining:
                        break
                    if not self._looks_like_kinship_hard_safe(text):
                        continue
                    candidate = self._build_safe_candidate(
                        text,
                        source_bucket="russian_kinship_hard_safe",
                        source_id=f"{dataset_id}:{split}:{index}:{text_index}",
                        metadata={
                            "dataset_id": dataset_id,
                            "split": split,
                            "kind": kind,
                            "license_check_required": True,
                            "safe_filter": "kinship_terms+moderation_export_relabeler_v1",
                        },
                    )
                    if candidate:
                        candidates.append(candidate)
                        accepted_for_dataset += 1

        return candidates

    def _build_safe_candidate(
        self,
        text: str,
        *,
        source_bucket: str,
        source_id: str,
        metadata: dict[str, Any],
    ) -> ModerationDatasetCandidate | None:
        model_text = self._sanitizer.sanitize(text)
        if len(model_text) < 16:
            return None

        relabeled = self._relabeler.relabel_row(
            {
                "model_text": model_text,
                "labels": [ModerationLabel.SAFE.value],
                "primary_label": ModerationLabel.SAFE.value,
                "severity": 0,
            }
        )
        labels = relabeled.get("labels") or []
        if relabeled.get("primary_label") != ModerationLabel.SAFE.value or labels != [ModerationLabel.SAFE.value]:
            return None

        return ModerationDatasetCandidate(
            text=model_text,
            labels=[ModerationLabel.SAFE],
            primary_label=ModerationLabel.SAFE,
            source_bucket=source_bucket,
            source_id=source_id,
            severity=0,
            metadata=metadata,
        )

    def _chunk_text(self, text: str) -> list[str]:
        normalized = " ".join(text.split())
        chunks: list[str] = []
        start = 0
        chunk_size = 420
        overlap = 40
        while start < len(normalized) and len(chunks) < 40:
            end = min(len(normalized), start + chunk_size)
            if end < len(normalized):
                sentence_end = max(normalized.rfind(".", start, end), normalized.rfind("!", start, end), normalized.rfind("?", start, end))
                if sentence_end > start + 180:
                    end = sentence_end + 1
            chunk = normalized[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(normalized):
                break
            start = max(end - overlap, start + 1)
        return chunks

    def _extract_candidate_texts(self, row: dict[str, Any], *, kind: str) -> list[str]:
        if kind == "dialogue_qa":
            question = str(row.get("question") or "").strip()
            answer = str(row.get("answer") or "").strip()
            return [f"{question}\n{answer}"] if question and answer else []

        texts: list[str] = []
        for key in ("text", "dialogue", "conversation", "content", "message", "utterance", "answer", "question"):
            value = row.get(key)
            texts.extend(self._flatten_text_value(value))

        if not texts:
            texts.extend(self._flatten_text_value(row))

        chunks: list[str] = []
        for text in texts:
            chunks.extend(self._chunk_text(text))
        return chunks

    def _flatten_text_value(self, value: Any) -> list[str]:
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        if isinstance(value, list):
            texts: list[str] = []
            for item in value:
                texts.extend(self._flatten_text_value(item))
            return texts
        if isinstance(value, dict):
            texts: list[str] = []
            for item in value.values():
                texts.extend(self._flatten_text_value(item))
            return texts
        return []

    def _looks_like_kinship_hard_safe(self, text: str) -> bool:
        lowered = text.casefold()
        if any(self._contains_stem(lowered, term) for term in self._hard_safe_block_terms):
            return False
        if not any(self._contains_stem(lowered, term) for term in self._kinship_terms):
            return False
        return any(self._contains_stem(lowered, term) for term in self._home_context_terms)

    def _contains_stem(self, text: str, stem: str) -> bool:
        return re.search(rf"\b{re.escape(stem)}\w*\b", text) is not None


class HuggingFaceSpamLoader:
    def load_spam_dataset(self, dataset_id: str, split: str, *, limit: int) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        candidates: list[ModerationDatasetCandidate] = []

        for index, row in enumerate(dataset):
            if len(candidates) >= limit:
                break
            text = self._extract_text(row)
            if not text:
                continue
            label = self._extract_spam_label(row)
            candidates.append(
                ModerationDatasetCandidate(
                    text=text,
                    labels=[label],
                    primary_label=label,
                    source_bucket="russian_spam",
                    source_id=f"{dataset_id}:{split}:{index}",
                    severity=2 if label == ModerationLabel.SPAM else 0,
                    metadata={
                        "dataset_id": dataset_id,
                        "split": split,
                        "license_check_required": True,
                        "raw_label": self._raw_label(row),
                    },
                )
            )

        return candidates

    def load_russian_scam_spam_dataset(
        self,
        dataset_id: str,
        split: str,
        *,
        limit: int,
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        relabeler = ModerationExportRelabeler()
        sanitizer = TrainingTextSanitizer()
        candidates: list[ModerationDatasetCandidate] = []

        for index, row in enumerate(dataset):
            if len(candidates) >= limit:
                break
            if str(row.get("is_spam", "")).casefold() not in {"1", "true", "spam"}:
                continue

            text = self._extract_text(row)
            if not text or not self._looks_russian(text):
                continue

            model_text = sanitizer.sanitize(text)
            relabeled = relabeler.relabel_row(
                {
                    "model_text": model_text,
                    "labels": [ModerationLabel.SPAM.value],
                    "primary_label": ModerationLabel.SPAM.value,
                    "severity": 2,
                }
            )
            labels = [ModerationLabel(label) for label in relabeled.get("labels", [])]
            primary_label = ModerationLabel(str(relabeled.get("primary_label") or ModerationLabel.SPAM.value))
            if primary_label == ModerationLabel.SAFE:
                continue

            candidates.append(
                ModerationDatasetCandidate(
                    text=model_text,
                    labels=labels or [primary_label],
                    primary_label=primary_label,
                    source_bucket="russian_scam_spam_public",
                    source_id=f"{dataset_id}:{split}:{index}",
                    severity=int(relabeled.get("severity") or 2),
                    metadata={
                        "dataset_id": dataset_id,
                        "split": split,
                        "license": "apache-2.0",
                        "language_filter": "cyrillic_ratio",
                        "labeler": "moderation_export_relabeler_v1",
                        "raw_label": row.get("is_spam"),
                    },
                )
            )

        return candidates

    def _extract_text(self, row: dict[str, Any]) -> str:
        for key in ("text", "message", "content", "sms", "body"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return ""

    def _extract_spam_label(self, row: dict[str, Any]) -> ModerationLabel:
        raw = str(self._raw_label(row)).casefold()
        if raw in {"1", "true", "spam", "advertisement", "ad"}:
            return ModerationLabel.SPAM
        return ModerationLabel.SAFE

    def _raw_label(self, row: dict[str, Any]) -> object:
        for key in ("label", "labels", "target", "class", "is_spam", "spam"):
            if key in row:
                return row[key]
        return None

    def _looks_russian(self, text: str) -> bool:
        letters = [char for char in text.casefold() if char.isalpha()]
        if len(letters) < 12:
            return False
        cyrillic = sum(1 for char in letters if "а" <= char <= "я" or char == "ё")
        return cyrillic / len(letters) >= 0.35


class HuggingFaceUrlSecurityLoader:
    def load_malicious_url_dataset(
        self,
        dataset_id: str,
        split: str,
        *,
        limit: int,
        source_bucket: str,
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        candidates: list[ModerationDatasetCandidate] = []

        for index, row in enumerate(dataset):
            if len(candidates) >= limit:
                break
            url = str(row.get("url") or row.get("URL") or "").strip()
            if not url:
                continue
            raw_label = str(row.get("type") or row.get("label") or row.get("target") or "").casefold()
            if raw_label in {"benign", "0", "false", "legitimate"}:
                labels = [ModerationLabel.URL]
                primary_label = ModerationLabel.URL
                severity = 1
            elif raw_label in {"phishing", "malicious", "1", "true", "malignant"}:
                labels = [ModerationLabel.SCAM, ModerationLabel.URL]
                primary_label = ModerationLabel.SCAM
                severity = 4
            else:
                continue

            candidates.append(
                ModerationDatasetCandidate(
                    text=url,
                    labels=labels,
                    primary_label=primary_label,
                    source_bucket=source_bucket,
                    source_id=f"{dataset_id}:{split}:{index}",
                    severity=severity,
                    metadata={
                        "dataset_id": dataset_id,
                        "split": split,
                        "license_check_required": True,
                        "raw_label": raw_label,
                    },
                )
            )

        return candidates

    def load_discord_phishing_scam_dataset(
        self,
        dataset_id: str,
        split: str,
        *,
        limit: int,
        source_bucket: str,
    ) -> list[ModerationDatasetCandidate]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        dataset = load_dataset(dataset_id, split=split, streaming=True)
        relabeler = ModerationExportRelabeler()
        sanitizer = TrainingTextSanitizer()
        candidates: list[ModerationDatasetCandidate] = []

        for index, row in enumerate(dataset):
            if len(candidates) >= limit:
                break
            text = str(row.get("msg_content") or row.get("text") or row.get("message") or "").strip()
            if not text:
                continue
            raw_label = str(row.get("lable") or row.get("label") or "").casefold()
            if raw_label in {"1", "true", "scam", "phishing"}:
                base_labels = [ModerationLabel.SCAM, ModerationLabel.URL]
                severity = 4
            elif raw_label in {"0", "false", "safe", "ham"}:
                base_labels = [ModerationLabel.SAFE]
                severity = 0
            else:
                continue

            model_text = sanitizer.sanitize(text)
            relabeled = relabeler.relabel_row(
                {
                    "model_text": model_text,
                    "labels": [label.value for label in base_labels],
                    "primary_label": resolve_primary_label(base_labels).value,
                    "severity": severity,
                }
            )
            labels = [ModerationLabel(label) for label in relabeled.get("labels", [])]
            primary_label = ModerationLabel(str(relabeled.get("primary_label") or resolve_primary_label(base_labels).value))
            candidates.append(
                ModerationDatasetCandidate(
                    text=model_text,
                    labels=labels or [primary_label],
                    primary_label=primary_label,
                    source_bucket=source_bucket,
                    source_id=f"{dataset_id}:{split}:{index}",
                    severity=int(relabeled.get("severity") or severity),
                    metadata={
                        "dataset_id": dataset_id,
                        "split": split,
                        "license_check_required": True,
                        "labeler": "moderation_export_relabeler_v1",
                        "raw_label": raw_label,
                    },
                )
            )

        return candidates
