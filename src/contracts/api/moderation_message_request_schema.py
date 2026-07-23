from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from src.contracts.api.api_model import ApiModel
from src.contracts.api.metadata_schema import SafeMetadata


class PunishmentStatisticsSchema(ApiModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    window_days: int = Field(ge=1, le=3650)
    total_in_window: int = Field(default=0, ge=0)
    timeouts_in_window: int = Field(default=0, ge=0)
    ai_deleted_messages_in_window: int = Field(default=0, ge=0)
    bans_in_window: int = Field(default=0, ge=0)
    last_punishment_at: datetime | None = None


class UserModerationContextSchema(ApiModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    account_created_at: datetime | None = None
    joined_guild_at: datetime | None = None
    account_age_days: int | None = Field(default=None, ge=0)
    guild_membership_days: int | None = Field(default=None, ge=0)
    punishments: PunishmentStatisticsSchema


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
    event_type: Literal["CREATE", "UPDATE"] = "CREATE"
    user_context: UserModerationContextSchema | None = None

    @field_validator("created_at", "author_created_at", "member_joined_at", "recent_message_timestamps", "user_context")
    @classmethod
    def _require_timezone(cls, value: datetime | tuple[datetime, ...] | None) -> datetime | tuple[datetime, ...] | None:
        if isinstance(value, UserModerationContextSchema):
            timestamps = (value.account_created_at, value.joined_guild_at, value.punishments.last_punishment_at)
        else:
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
