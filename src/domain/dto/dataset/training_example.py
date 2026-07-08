from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.dataset.dataset_source import DatasetSource
from src.domain.dataset.feedback_type import FeedbackType
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel


class TrainingExample(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: int | None = None
    message_id: str
    model_text: str
    labels: list[ModerationLabel]
    primary_label: ModerationLabel
    severity: int = Field(ge=0, le=5)
    source: DatasetSource
    features: dict[str, Any] = Field(default_factory=dict)
    rule_matches: list[str] = Field(default_factory=list)
    risk_score: float = Field(ge=0.0, le=100.0)
    decision_action: ModerationAction
    feedback_type: FeedbackType | None = None
    model_version: str | None = None
    policy_version: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
