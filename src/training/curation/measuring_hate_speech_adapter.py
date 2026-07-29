from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.dataset_split_assigner import DatasetSplitAssigner
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema


class MeasuringHateSpeechAdapter:
    REPO_ID = "ucberkeley-dlab/measuring-hate-speech"
    REVISION = "5468f6e118396646b02a2f691e771f6b6d9502ea"
    LICENSE = "CC-BY-4.0"

    _COLUMNS = (
        "comment_id",
        "text",
        "hate_speech_score",
        "insult",
        "humiliate",
        "violence",
        "genocide",
        "target_race",
        "target_gender",
    )

    def __init__(
        self,
        *,
        schema: ModerationDatasetSchema,
        split_assigner: DatasetSplitAssigner,
    ) -> None:
        self._schema = schema
        self._split_assigner = split_assigner

    def build(self, *, output_dir: Path) -> dict[str, Any]:
        from datasets import load_dataset

        dataset = load_dataset(
            self.REPO_ID,
            split="train",
            revision=self.REVISION,
        ).select_columns(list(self._COLUMNS))

        aggregates: dict[int, dict[str, Any]] = {}
        for row in dataset:
            comment_id = int(row["comment_id"])
            state = aggregates.setdefault(
                comment_id,
                {
                    "text": str(row["text"]),
                    "count": 0,
                    "hate_speech_score": 0.0,
                    "insult": 0.0,
                    "humiliate": 0.0,
                    "violence": 0.0,
                    "genocide": 0.0,
                    "target_race": 0,
                    "target_gender": 0,
                },
            )
            state["count"] += 1
            for field in ("hate_speech_score", "insult", "humiliate", "violence", "genocide"):
                state[field] += float(row[field] or 0.0)
            state["target_race"] += int(bool(row["target_race"]))
            state["target_gender"] += int(bool(row["target_gender"]))

        output_dir.mkdir(parents=True, exist_ok=True)
        counts: Counter[str] = Counter()
        handles = {
            split: (output_dir / f"{split}.jsonl").open("a", encoding="utf-8", newline="\n")
            for split in ("train", "validation")
        }

        try:
            for comment_id, state in aggregates.items():
                count = state["count"]
                race_ratio = state["target_race"] / count
                gender_ratio = state["target_gender"] / count
                topics = tuple(
                    topic
                    for topic, ratio in (("race", race_ratio), ("gender", gender_ratio))
                    if ratio >= 0.5
                )
                if not topics:
                    counts["skipped_without_target_topic"] += 1
                    continue

                score = state["hate_speech_score"] / count
                labels: set[ModerationLabel]
                severity: int
                if score > 0.5:
                    labels = {ModerationLabel.HATE, ModerationLabel.TOXIC}
                    severity = 4
                    mean_violence = state["violence"] / count
                    mean_genocide = state["genocide"] / count
                    if mean_violence >= 2.0 or mean_genocide >= 1.0:
                        labels.add(ModerationLabel.THREAT)
                        severity = 5
                elif score < -1.0:
                    labels = {ModerationLabel.SAFE}
                    severity = 0
                else:
                    counts["skipped_ambiguous_score"] += 1
                    continue

                text = state["text"]
                split = self._split_assigner.assign(text)
                record = self._schema.build_row(
                    text=text,
                    labels=labels,
                    severity=severity,
                    record_id=f"mhs_{comment_id}",
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
            "unique_comments": len(aggregates),
            "counts": dict(counts),
        }
