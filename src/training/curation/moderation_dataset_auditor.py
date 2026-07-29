from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema
from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher


class ModerationDatasetAuditor:
    _TOPIC_LABELS = {
        "race": (ModerationLabel.TOXIC, ModerationLabel.HATE, ModerationLabel.THREAT),
        "gender": (ModerationLabel.TOXIC, ModerationLabel.HATE, ModerationLabel.THREAT),
        "family": (
            ModerationLabel.TOXIC,
            ModerationLabel.HATE,
            ModerationLabel.THREAT,
            ModerationLabel.NSFW,
        ),
    }

    def __init__(
        self,
        *,
        schema: ModerationDatasetSchema,
        matcher: SensitiveTopicMatcher,
    ) -> None:
        self._schema = schema
        self._matcher = matcher

    def audit(self, *, dataset_dir: Path, report_path: Path) -> dict[str, Any]:
        split_keys: dict[str, set[bytes]] = {}
        split_reports: dict[str, dict[str, Any]] = {}

        for split in ("train", "validation"):
            report, keys = self._audit_file(dataset_dir / f"{split}.jsonl")
            split_reports[split] = report
            split_keys[split] = keys

        cross_overlap = len(split_keys["train"] & split_keys["validation"])
        gaps = self._find_gaps(split_reports)
        report = {
            "dataset_dir": str(dataset_dir),
            "schema_labels": self._schema.label_names,
            "splits": split_reports,
            "cross_split_normalized_overlap": cross_overlap,
            "data_gaps": gaps,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return report

    def _audit_file(self, path: Path) -> tuple[dict[str, Any], set[bytes]]:
        rows = 0
        duplicate_texts = 0
        duplicate_ids = 0
        vector_mismatches = 0
        primary_label_mismatches = 0
        severity_mismatches = 0
        label_counts: Counter[str] = Counter()
        primary_counts: Counter[str] = Counter()
        topic_mentions: Counter[str] = Counter()
        topic_label_counts: dict[str, Counter[str]] = defaultdict(Counter)
        auto_rule_misses = 0
        keys: set[bytes] = set()
        ids: set[tuple[str, str]] = set()

        with path.open("r", encoding="utf-8-sig") as source:
            for line_number, raw in enumerate(source, 1):
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
                normalized = self._schema.normalize_row(row)
                raw_vector = row.get("labels")
                if (
                    not isinstance(raw_vector, list)
                    or len(raw_vector) != len(self._schema.labels)
                    or [float(value) for value in raw_vector] != normalized["labels"]
                ):
                    vector_mismatches += 1
                if row.get("primary_label") != normalized["primary_label"]:
                    primary_label_mismatches += 1
                if int(row.get("severity", 0)) != normalized["severity"]:
                    severity_mismatches += 1
                rows += 1

                key = self._text_digest(str(row["text"]))
                if key in keys:
                    duplicate_texts += 1
                keys.add(key)

                record_id = (type(row["id"]).__name__, str(row["id"]))
                if record_id in ids:
                    duplicate_ids += 1
                ids.add(record_id)

                selected = {ModerationLabel(name) for name in row["label_names"]}
                label_counts.update(row["label_names"])
                primary_counts[str(row["primary_label"])] += 1

                annotation = self._matcher.annotate(str(row["text"]))
                topic_mentions.update(annotation.topics)
                for topic in annotation.topics:
                    topic_label_counts[topic].update(label.value for label in selected)
                if set(annotation.labels) - selected:
                    auto_rule_misses += 1

        return (
            {
                "path": str(path),
                "rows": rows,
                "unique_normalized_texts": len(keys),
                "duplicate_normalized_texts": duplicate_texts,
                "duplicate_ids": duplicate_ids,
                "structural_issues": {
                    "vector_mismatches": vector_mismatches,
                    "primary_label_mismatches": primary_label_mismatches,
                    "severity_mismatches": severity_mismatches,
                },
                "label_counts": dict(label_counts),
                "primary_label_counts": dict(primary_counts),
                "topic_mentions": dict(topic_mentions),
                "topic_label_counts": {
                    topic: dict(counts)
                    for topic, counts in topic_label_counts.items()
                },
                "high_confidence_rule_misses": auto_rule_misses,
            },
            keys,
        )

    def _find_gaps(self, split_reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []
        train_counts = split_reports["train"]["label_counts"]
        validation_counts = split_reports["validation"]["label_counts"]

        for label in self._schema.label_names:
            train_count = int(train_counts.get(label, 0))
            validation_count = int(validation_counts.get(label, 0))
            if train_count < 2_000 or validation_count < 200:
                gaps.append(
                    {
                        "scope": "overall",
                        "label": label,
                        "train": train_count,
                        "validation": validation_count,
                        "recommended_minimum": {"train": 2_000, "validation": 200},
                    }
                )

        for topic, labels in self._TOPIC_LABELS.items():
            train_topic = split_reports["train"]["topic_label_counts"].get(topic, {})
            validation_topic = split_reports["validation"]["topic_label_counts"].get(topic, {})
            for label in labels:
                train_count = int(train_topic.get(label.value, 0))
                validation_count = int(validation_topic.get(label.value, 0))
                if train_count < 500 or validation_count < 50:
                    gaps.append(
                        {
                            "scope": topic,
                            "label": label.value,
                            "train": train_count,
                            "validation": validation_count,
                            "recommended_minimum": {"train": 500, "validation": 50},
                        }
                    )
        return gaps

    @staticmethod
    def _text_digest(text: str) -> bytes:
        normalized = SensitiveTopicMatcher.normalize_text(text)
        return hashlib.blake2b(normalized.encode("utf-8"), digest_size=16).digest()
