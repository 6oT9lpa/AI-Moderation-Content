from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.decision.moderation_decision import ModerationDecision


class ActionExecutionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    moderation_decision: ModerationDecision
    platform: str
    guild_id: str | None = None
    chat_id: str | None = None
    channel_id: str | None = None
    message_id: str
    user_id: str
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)
