from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SyntheticDiscordAuthor:
    id: str
    bot: bool = False


@dataclass(frozen=True)
class SyntheticDiscordMessage:
    id: str
    guild_id: str
    channel_id: str
    author: SyntheticDiscordAuthor
    content: str
    created_at: datetime
    attachment_count: int = 0
    embed_count: int = 0
    referenced_message_id: str | None = None


@dataclass(frozen=True)
class SyntheticDiscordBotPayload:
    moderation_payload: dict[str, object]
    action_result_payload: dict[str, object] | None
