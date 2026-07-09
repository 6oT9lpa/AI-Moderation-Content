from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from src.domain.dataset.feedback_type import FeedbackType
from src.domain.dto.dataset.dataset_collection_record import DatasetCollectionRecord
from src.domain.dto.dataset.dataset_export_policy import DatasetExportPolicy
from src.domain.dto.dataset.training_example import TrainingExample
from src.domain.moderation.moderation_label import ModerationLabel
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class DatasetExportBuilder:
    def build_training_examples(
        self,
        records: list[DatasetCollectionRecord],
        policy: DatasetExportPolicy | None = None,
        *,
        now: datetime | None = None,
    ) -> list[TrainingExample]:
        current_policy = policy or DatasetExportPolicy()
        current_time = self._normalize_datetime(now or datetime.now(timezone.utc))
        selected: list[TrainingExample] = []
        primary_label_counts: dict[ModerationLabel, int] = defaultdict(int)

        for record in records:
            if not self._passes_quality_filters(record, current_policy, current_time):
                continue

            example = record.training_example
            primary_label = example.primary_label

            if (
                current_policy.max_examples_per_primary_label is not None
                and primary_label_counts[primary_label] >= current_policy.max_examples_per_primary_label
            ):
                continue

            selected.append(example)
            primary_label_counts[primary_label] += 1

        logger.info(
            "Dataset export built input_records=%s output_examples=%s label_counts=%s",
            len(records),
            len(selected),
            {label.value: count for label, count in primary_label_counts.items()},
        )
        return selected

    def _passes_quality_filters(
        self,
        record: DatasetCollectionRecord,
        policy: DatasetExportPolicy,
        now: datetime,
    ) -> bool:
        example = record.training_example

        if not policy.include_empty_model_text and not example.model_text.strip():
            return False

        if not policy.include_injection_marked and record.text.injection_markers:
            return False

        if policy.allowed_sources is not None and example.source not in policy.allowed_sources:
            return False

        created_at = self._normalize_datetime(example.created_at)
        if policy.min_created_at is not None and created_at < self._normalize_datetime(policy.min_created_at):
            return False

        if policy.max_created_at is not None and created_at > self._normalize_datetime(policy.max_created_at):
            return False

        if (
            not policy.include_expired_retention
            and record.retention_until is not None
            and self._normalize_datetime(record.retention_until) <= now
        ):
            return False

        feedback_type = self._resolve_feedback_type(record)
        if policy.require_feedback and feedback_type is None:
            return False

        if feedback_type is not None and feedback_type not in policy.allowed_feedback_types:
            return False

        return True

    def _resolve_feedback_type(self, record: DatasetCollectionRecord) -> FeedbackType | None:
        if record.feedback is not None:
            return record.feedback.feedback_type

        return record.training_example.feedback_type

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)
