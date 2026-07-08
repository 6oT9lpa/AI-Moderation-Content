from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.domain.dataset.feedback_type import FeedbackType
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel


class DatasetFeedbackLabel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    labels: list[ModerationLabel] = Field(default_factory=list)
    primary_label: ModerationLabel | None = None
    scam_subtype: str | None = None
    severity: int | None = Field(default=None, ge=0, le=5)
    recommended_action: ModerationAction | None = None
    moderator_id: str | None = None
    feedback_type: FeedbackType
    is_false_positive: bool = False
    is_false_negative: bool = False
    needs_context: bool = False
    annotator_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    annotation_source: str | None = None
    notes: str | None = None
