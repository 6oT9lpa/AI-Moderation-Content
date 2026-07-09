from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.moderation.moderation_label import ModerationLabel


class ModerationDatasetCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    labels: list[ModerationLabel]
    primary_label: ModerationLabel
    source_bucket: str
    source_id: str
    severity: int = Field(ge=0, le=5)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_negative(self) -> bool:
        return self.primary_label != ModerationLabel.SAFE
