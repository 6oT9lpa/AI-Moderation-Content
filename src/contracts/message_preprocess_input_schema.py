from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _msk_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=3), name="MSK"))


class MessagePreprocessInputSchema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    MAX_TEXT_LENGTH: ClassVar[int] = 8_000
    MAX_RECENT_MESSAGES: ClassVar[int] = 20
    MAX_METADATA_BYTES: ClassVar[int] = 16_384

    platform: str = "discord"
    guild_id: str = "0"
    channel_id: str
    user_id: str
    message_id: str

    raw_text: str = Field(default="", max_length=MAX_TEXT_LENGTH)
    created_at: datetime = Field(default_factory=_msk_now)

    author_created_at: datetime | None = None
    member_joined_at: datetime | None = None
    reply_to_message_id: str | None = None

    mention_count: int = 0
    role_mention_count: int = 0
    channel_mention_count: int = 0

    has_attachments: bool = False
    attachment_count: int = 0

    recent_messages: tuple[str, ...] = Field(default=(), max_length=MAX_RECENT_MESSAGES)
    recent_message_timestamps: tuple[datetime, ...] = Field(default=(), max_length=MAX_RECENT_MESSAGES)
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

    @field_validator("recent_messages")
    @classmethod
    def _validate_recent_messages(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(len(value) > cls.MAX_TEXT_LENGTH for value in values):
            raise ValueError("recent message exceeds maximum length")
        return values

    @field_validator("metadata")
    @classmethod
    def _validate_metadata_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            payload = json.dumps(value, default=str, ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be JSON serializable") from exc
        if len(payload) > cls.MAX_METADATA_BYTES:
            raise ValueError("metadata exceeds maximum size")
        return value
