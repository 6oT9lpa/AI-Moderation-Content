from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema
from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher


class SensitiveTopicRelabeler:
    _REVIEW_RELEVANT_LABELS = frozenset(
        {
            ModerationLabel.TOXIC,
            ModerationLabel.PROFANITY,
            ModerationLabel.HATE,
            ModerationLabel.THREAT,
            ModerationLabel.NSFW,
        }
    )

    def __init__(
        self,
        *,
        schema: ModerationDatasetSchema,
        matcher: SensitiveTopicMatcher,
    ) -> None:
        self._schema = schema
        self._matcher = matcher

    def relabel_file(
        self,
        *,
        input_path: Path,
        output_path: Path,
        changes_path: Path,
        review_path: Path,
    ) -> dict[str, Any]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        changes_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.parent.mkdir(parents=True, exist_ok=True)

        rows = 0
        changed = 0
        review_candidates = 0
        topic_mentions: Counter[str] = Counter()
        added_labels: Counter[str] = Counter()
        labels_before: Counter[str] = Counter()
        labels_after: Counter[str] = Counter()

        with (
            input_path.open("r", encoding="utf-8-sig") as source,
            output_path.open("w", encoding="utf-8", newline="\n") as output,
            changes_path.open("w", encoding="utf-8", newline="\n") as changes,
            review_path.open("w", encoding="utf-8", newline="\n") as review,
        ):
            for line_number, raw in enumerate(source, 1):
                if not raw.strip():
                    continue

                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at {input_path}:{line_number}") from exc

                annotation = self._matcher.annotate(str(row.get("text", "")))
                current_labels = {ModerationLabel(name) for name in row.get("label_names", [])}
                current_labels = current_labels or {ModerationLabel.SAFE}
                new_labels = set(annotation.labels) - current_labels
                normalized = self._schema.normalize_row(
                    row,
                    added_labels=annotation.labels,
                    minimum_severity=annotation.severity,
                )

                rows += 1
                topic_mentions.update(annotation.topics)
                labels_before.update(label.value for label in current_labels)
                labels_after.update(normalized["label_names"])

                if new_labels:
                    changed += 1
                    added_labels.update(label.value for label in new_labels)
                    changes.write(
                        json.dumps(
                            {
                                "id": row.get("id"),
                                "text": row.get("text"),
                                "topics": annotation.topics,
                                "labels_before": sorted(label.value for label in current_labels),
                                "labels_after": normalized["label_names"],
                                "severity_before": row.get("severity"),
                                "severity_after": normalized["severity"],
                                "reasons": annotation.reasons,
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )

                if self._requires_review(annotation.requires_review, current_labels):
                    review_candidates += 1
                    review.write(
                        json.dumps(
                            {
                                "id": row.get("id"),
                                "text": row.get("text"),
                                "topics": annotation.topics,
                                "current_labels": sorted(label.value for label in current_labels),
                                "severity": row.get("severity"),
                                "reasons": annotation.reasons,
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )

                output.write(json.dumps(normalized, ensure_ascii=False, separators=(",", ":")) + "\n")

        return {
            "input": str(input_path),
            "output": str(output_path),
            "rows": rows,
            "changed_rows": changed,
            "review_candidates": review_candidates,
            "topic_mentions": dict(topic_mentions),
            "added_labels": dict(added_labels),
            "labels_before": dict(labels_before),
            "labels_after": dict(labels_after),
            "changes_path": str(changes_path),
            "review_path": str(review_path),
        }

    def _requires_review(
        self,
        annotation_requires_review: bool,
        current_labels: set[ModerationLabel],
    ) -> bool:
        return annotation_requires_review and bool(current_labels & self._REVIEW_RELEVANT_LABELS)
