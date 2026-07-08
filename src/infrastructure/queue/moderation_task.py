from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(slots=True, frozen=True)
class ModerationTask:
    source_platform: str
    space_id: str
    channel_id: str
    message_id: str
    payload: Any
    priority: int = 100
    attempts: int = 0
    correlation_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def partition_key(self) -> str:
        return f"{self.source_platform}:{self.space_id}:{self.channel_id}"
