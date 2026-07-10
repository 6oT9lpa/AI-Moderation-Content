from datetime import datetime

from pydantic import Field, field_validator

from src.contracts.api.api_model import ApiModel
from src.contracts.api.metadata_schema import SafeMetadata


class ModerationMessageRequestSchema(ApiModel):
    platform: str = Field(default="discord", min_length=1, max_length=32, pattern=r"^[a-z0-9_-]+$")
    guild_id: str = Field(min_length=1, max_length=32, pattern=r"^[0-9A-Za-z_-]+$")
    channel_id: str = Field(min_length=1, max_length=32, pattern=r"^[0-9A-Za-z_-]+$")
    user_id: str = Field(min_length=1, max_length=64, pattern=r"^[0-9A-Za-z_-]+$")
    message_id: str = Field(min_length=1, max_length=64, pattern=r"^[0-9A-Za-z_-]+$")
    raw_text: str = Field(default="", max_length=8_000)
    created_at: datetime
    author_created_at: datetime | None = None
    member_joined_at: datetime | None = None
    reply_to_message_id: str | None = Field(default=None, max_length=64, pattern=r"^[0-9A-Za-z_-]+$")
    mention_count: int = Field(default=0, ge=0, le=100)
    role_mention_count: int = Field(default=0, ge=0, le=100)
    channel_mention_count: int = Field(default=0, ge=0, le=100)
    has_attachments: bool = False
    attachment_count: int = Field(default=0, ge=0, le=50)
    recent_messages: tuple[str, ...] = Field(default=(), max_length=20)
    recent_message_timestamps: tuple[datetime, ...] = Field(default=(), max_length=20)
    metadata: SafeMetadata = Field(default_factory=dict, max_length=64)

    @field_validator("created_at", "author_created_at", "member_joined_at", "recent_message_timestamps")
    @classmethod
    def _require_timezone(cls, value: datetime | tuple[datetime, ...] | None) -> datetime | tuple[datetime, ...] | None:
        timestamps = value if isinstance(value, tuple) else (value,)
        if any(item is not None and item.tzinfo is None for item in timestamps):
            raise ValueError("timestamps must include a timezone")
        return value

    @field_validator("recent_messages")
    @classmethod
    def _limit_recent_messages(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(len(item) > 1_000 for item in value):
            raise ValueError("recent message exceeds maximum length")
        return value
