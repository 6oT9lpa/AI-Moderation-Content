from __future__ import annotations

import json
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
