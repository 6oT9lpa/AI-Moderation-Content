from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _msk_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=3), name="MSK"))


class MessagePreprocessInputSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    platform: str = "discord"
    guild_id: str = "0"
    channel_id: str
    user_id: str
    message_id: str

    raw_text: str = ""
    created_at: datetime = Field(default_factory=_msk_now)

    author_created_at: datetime | None = None
    member_joined_at: datetime | None = None
    reply_to_message_id: str | None = None

    mention_count: int = 0
    role_mention_count: int = 0
    channel_mention_count: int = 0

    has_attachments: bool = False
    attachment_count: int = 0

    recent_messages: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "mention_count",
        "role_mention_count",
        "channel_mention_count",
        "attachment_count",
    )

    @classmethod
    def _validate_non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("value must be greater than or equal to 0")
        return value
