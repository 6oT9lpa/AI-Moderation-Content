from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.dataset_split_assigner import DatasetSplitAssigner
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema
from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher


class RussianFamilyToxicAdapter:
    TOXIC_REPO_ID = "klamas/russian-toxic"
    TOXIC_REVISION = "eea2e077780960596524fc5bffcdd473775edaed"
    TOXIC_LICENSE = "MIT"
    THREAT_REPO_ID = "IvanFed/russian-toxic-comments-multilabel"
    THREAT_REVISION = "ac1ea37cb7b85cfec6f09ba22f71d4fe487b43d7"
    THREAT_LICENSE = "Apache-2.0"

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

        toxic_dataset = concatenate_datasets(
            [
                load_dataset(
                    self.TOXIC_REPO_ID,
                    split=split,
                    revision=self.TOXIC_REVISION,
                ).select_columns(["text", "label"])
                for split in ("train", "test")
            ]
        )
        threat_dataset = concatenate_datasets(
            [
                load_dataset(
                    self.THREAT_REPO_ID,
                    split=split,
                    revision=self.THREAT_REVISION,
                ).select_columns(["text", "threat"])
                for split in ("train", "validation", "test")
            ]
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        counts: Counter[str] = Counter()
        handles = {
            split: (output_dir / f"{split}.jsonl").open(
                "w",
                encoding="utf-8",
                newline="\n",
            )
            for split in ("train", "validation")
        }

        try:
            for row_index, row in enumerate(toxic_dataset):
                counts["toxic_upstream_rows"] += 1
                if int(row["label"]) != 1:
                    continue
                self._write_if_targeted(
                    text=str(row["text"]),
                    required_label=ModerationLabel.TOXIC,
                    record_id=f"klamas_family_{row_index}",
                    handles=handles,
                    counts=counts,
                    source_key="toxic",
                )

            for row_index, row in enumerate(threat_dataset):
                counts["threat_upstream_rows"] += 1
                if int(row["threat"]) != 1:
                    continue
                self._write_if_targeted(
                    text=str(row["text"]),
                    required_label=ModerationLabel.THREAT,
                    record_id=f"ivanfed_family_threat_{row_index}",
                    handles=handles,
                    counts=counts,
                    source_key="threat",
                )
        finally:
            for handle in handles.values():
                handle.close()

        return {
            "sources": [
                {
                    "repo_id": self.TOXIC_REPO_ID,
                    "revision": self.TOXIC_REVISION,
                    "license": self.TOXIC_LICENSE,
                    "upstream_rows": len(toxic_dataset),
                },
                {
                    "repo_id": self.THREAT_REPO_ID,
                    "revision": self.THREAT_REVISION,
                    "license": self.THREAT_LICENSE,
                    "upstream_rows": len(threat_dataset),
                },
            ],
            "counts": dict(counts),
        }

    def _write_if_targeted(
        self,
        *,
        text: str,
        required_label: ModerationLabel,
        record_id: str,
        handles: dict[str, Any],
        counts: Counter[str],
        source_key: str,
    ) -> None:
        annotation = self._matcher.annotate(text)
        if "family" not in annotation.topics:
            counts[f"{source_key}_skipped_without_family"] += 1
            return
        if required_label not in annotation.labels:
            counts[f"{source_key}_review_not_targeted"] += 1
            return

        split = self._split_assigner.assign(text)
        record = self._schema.build_row(
            text=text,
            labels=annotation.labels,
            severity=annotation.severity,
            record_id=record_id,
        )
        handles[split].write(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        counts[f"{source_key}_written_{split}"] += 1
        counts.update(f"{source_key}_label_{label.value}" for label in annotation.labels)
