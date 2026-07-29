from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.dataset_split_assigner import DatasetSplitAssigner
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema
from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher


class CivilCommentsAdapter:
    REPO_ID = "google/civil_comments"
    REVISION = "f2970eb3a55777454c94069077cc8d9b5866312d"
    LICENSE = "CC0-1.0"

    _COLUMNS = (
        "text",
        "toxicity",
        "severe_toxicity",
        "obscene",
        "threat",
        "insult",
        "identity_attack",
        "sexual_explicit",
    )

    def __init__(
        self,
        *,
        schema: ModerationDatasetSchema,
        matcher: SensitiveTopicMatcher,
        split_assigner: DatasetSplitAssigner,
    ) -> None:
        self._schema = schema
        self._matcher = matcher
        self._split_assigner = split_assigner

    def build(self, *, output_dir: Path) -> dict[str, Any]:
        from datasets import concatenate_datasets, load_dataset

        dataset = concatenate_datasets(
            [
                load_dataset(
                    self.REPO_ID,
                    split=split,
                    revision=self.REVISION,
                ).select_columns(list(self._COLUMNS))
                for split in ("validation", "test")
            ]
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        counts: Counter[str] = Counter()
        handles = {
            split: (output_dir / f"{split}.jsonl").open("a", encoding="utf-8", newline="\n")
            for split in ("train", "validation")
        }

        try:
            for row_index, row in enumerate(dataset):
                text = str(row["text"])
                topics = self._matcher.detect_topics(text)
                if not topics:
                    counts["skipped_without_target_topic"] += 1
                    continue

                labels, severity = self._labels_for_row(row, topics)
                if labels is None:
                    counts["skipped_ambiguous_scores"] += 1
                    continue

                split = self._split_assigner.assign(text)
                record = self._schema.build_row(
                    text=text,
                    labels=labels,
                    severity=severity,
                    record_id=f"civil_{row_index}",
                )
                handles[split].write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                counts[f"written_{split}"] += 1
                counts.update(f"topic_{topic}" for topic in topics)
                counts.update(f"label_{label.value}" for label in labels)
        finally:
            for handle in handles.values():
                handle.close()

        return {
            "source": self.REPO_ID,
            "revision": self.REVISION,
            "license": self.LICENSE,
            "upstream_rows": len(dataset),
            "counts": dict(counts),
        }

    @staticmethod
    def _labels_for_row(
        row: dict[str, Any],
        topics: tuple[str, ...],
    ) -> tuple[set[ModerationLabel] | None, int]:
        labels: set[ModerationLabel] = set()
        severity = 0
        is_group_topic = bool({"race", "gender"} & set(topics))

        if float(row["threat"]) >= 0.5:
            labels.update((ModerationLabel.THREAT, ModerationLabel.TOXIC))
            severity = 5
        if float(row["sexual_explicit"]) >= 0.5:
            labels.add(ModerationLabel.NSFW)
            if "family" in topics:
                labels.add(ModerationLabel.TOXIC)
            severity = max(severity, 4)
        if float(row["identity_attack"]) >= 0.5 and is_group_topic:
            labels.update((ModerationLabel.HATE, ModerationLabel.TOXIC))
            severity = max(severity, 4)
        if (
            float(row["toxicity"]) >= 0.7
            or float(row["insult"]) >= 0.7
            or float(row["severe_toxicity"]) >= 0.5
        ):
            labels.add(ModerationLabel.TOXIC)
            severity = max(severity, 3)
        if float(row["obscene"]) >= 0.7:
            labels.add(ModerationLabel.PROFANITY)
            severity = max(severity, 1)

        if labels:
            return labels, severity

        maximum_score = max(
            float(row[column])
            for column in CivilCommentsAdapter._COLUMNS
            if column != "text"
        )
        if maximum_score <= 0.1:
            return {ModerationLabel.SAFE}, 0
        return None, 0
