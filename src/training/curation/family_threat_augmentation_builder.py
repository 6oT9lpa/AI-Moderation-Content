from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.dataset_split_assigner import DatasetSplitAssigner
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema
from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher


class FamilyThreatAugmentationBuilder:
    _PREFIXES = (
        "",
        "слышишь, ",
        "запомни: ",
        "если не отстанешь, ",
    )
    _TARGETS = (
        "твою мать",
        "твоего отца",
        "твоих родителей",
        "всю твою семью",
        "твоих родных",
        "твою сестру",
        "твоего брата",
        "твою жену",
        "твоего мужа",
        "твоего сына",
        "твою дочь",
        "твоих родственников",
        "твою бабушку",
        "твоего дедушку",
        "твоих близких",
        "всю твою родню",
    )
    _THREATS = (
        "я убью {target}",
        "я зарежу {target}",
        "я изобью {target}",
        "я покалечу {target}",
        "я найду {target} и застрелю",
        "я пристрелю {target}",
        "я повешу {target}",
        "я утоплю {target}",
        "хочу убить {target}",
        "пора избить {target}",
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
            for row_index, text in enumerate(self._candidate_texts()):
                annotation = self._matcher.annotate(text)
                required = {ModerationLabel.THREAT, ModerationLabel.TOXIC}
                if "family" not in annotation.topics or not required.issubset(
                    annotation.labels
                ):
                    raise RuntimeError(
                        f"Synthetic family threat failed matcher validation: {text!r}"
                    )
                if ModerationLabel.HATE in annotation.labels:
                    raise RuntimeError(
                        f"Family-only threat must not be labelled HATE: {text!r}"
                    )

                split = self._split_assigner.assign(text)
                record = self._schema.build_row(
                    text=text,
                    labels=annotation.labels,
                    severity=annotation.severity,
                    record_id=f"family_threat_aug_{row_index}",
                )
                handles[split].write(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
                counts[f"written_{split}"] += 1
                counts.update(f"label_{label.value}" for label in annotation.labels)
        finally:
            for handle in handles.values():
                handle.close()

        return {
            "source": "matcher_validated_family_threat_templates",
            "license": "project-generated",
            "counts": dict(counts),
        }

    def _candidate_texts(self) -> Iterator[str]:
        for prefix in self._PREFIXES:
            for target in self._TARGETS:
                for threat in self._THREATS:
                    yield prefix + threat.format(target=target)
