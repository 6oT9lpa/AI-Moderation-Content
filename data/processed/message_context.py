from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True, frozen=True)
class MessageContext:
    guild_id: int
    channel_id: int
    author_id: int
    message_id: int

    created_at: datetime

    raw_text: str
    normalized_text: str

    urls: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()

    has_url: bool = False
    has_invite: bool = False

    message_length: int = 0
    words_count: int = 0

    emoji_count: int = 0
    mentions_count: int = 0
    role_mentions_count: int = 0

    caps_ratio: float = 0.0
    digits_ratio: float = 0.0

    repeated_chars: bool = False

    has_zero_width: bool = False
    has_homoglyphs: bool = False

    account_age_days: int = 0

    recent_messages: tuple[str, ...] = ()

    metadata: dict[str, Any] = field(default_factory=dict)