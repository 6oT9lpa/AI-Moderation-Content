from pydantic import Field, model_validator

from src.contracts.api.api_model import ApiModel
from src.domain.dataset.feedback_type import FeedbackType
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel


class ModerationFeedbackRequestSchema(ApiModel):
    event_id: int | None = Field(default=None, gt=0)
    message_id: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[0-9A-Za-z_-]+$")
    feedback_type: FeedbackType
    labels: tuple[ModerationLabel, ...] = Field(default=(), max_length=14)
    primary_label: ModerationLabel | None = None
    severity: int | None = Field(default=None, ge=0, le=5)
    recommended_action: ModerationAction | None = None
    moderator_id: str | None = Field(default=None, max_length=128, pattern=r"^[a-f0-9]{64}$")
    annotation_source: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def _require_reference(self) -> "ModerationFeedbackRequestSchema":
        if self.event_id is None and self.message_id is None:
            raise ValueError("event_id or message_id is required")
        return self
