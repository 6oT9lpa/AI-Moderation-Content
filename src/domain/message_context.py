from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.domain import MessageFeatures


@dataclass(slots=True, frozen=True)
class MessageContext:
    platform: str
    guild_id: str
    channel_id: str
    user_id: str
    message_id: str

    created_at: datetime

    raw_text: str
    normalized_text: str
    text_hash: str
    language: str

    reply_to_message_id: str | None = None

    urls: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    invites: tuple[str, ...] = ()

    has_url: bool = False
    has_invite: bool = False
    has_shortener: bool = False

    has_attachments: bool = False
    attachment_count: int = 0

    account_age_days: int | None = None
    member_age_days: int | None = None

    recent_messages: tuple[str, ...] = ()

    features: MessageFeatures | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
