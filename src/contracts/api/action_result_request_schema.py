from datetime import datetime

from pydantic import Field, field_validator, model_validator

from src.contracts.api.api_model import ApiModel
from src.domain.action.action_execution_status import ActionExecutionStatus
from src.domain.moderation.moderation_action import ModerationAction


class ActionResultRequestSchema(ApiModel):
    event_id: int | None = Field(default=None, gt=0)
    message_id: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[0-9A-Za-z_-]+$")
    action: ModerationAction
    status: ActionExecutionStatus
    dry_run: bool
    platform_error_code: str | None = Field(default=None, max_length=64, pattern=r"^[A-Z0-9_:-]+$")
    platform_error_message: str | None = Field(default=None, max_length=256)
    timestamp: datetime

    @model_validator(mode="after")
    def _require_reference(self) -> "ActionResultRequestSchema":
        if self.event_id is None and self.message_id is None:
            raise ValueError("event_id or message_id is required")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return self

    @field_validator("status")
    @classmethod
    def _reject_pending_status(cls, value: ActionExecutionStatus) -> ActionExecutionStatus:
        if value == ActionExecutionStatus.PENDING:
            raise ValueError("action result must be final")
        return value
