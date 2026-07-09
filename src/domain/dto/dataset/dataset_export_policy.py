from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.domain.dataset.dataset_source import DatasetSource
from src.domain.dataset.feedback_type import FeedbackType


class DatasetExportPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed_feedback_types: set[FeedbackType] = Field(
        default_factory=lambda: {
            FeedbackType.CONFIRMED,
            FeedbackType.CORRECTED,
        }
    )
    allowed_sources: set[DatasetSource] | None = None
    min_created_at: datetime | None = None
    max_created_at: datetime | None = None
    max_examples_per_primary_label: int | None = Field(default=None, gt=0)
    require_feedback: bool = True
    include_expired_retention: bool = False
    include_empty_model_text: bool = False
    include_injection_marked: bool = False
