from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone

from src.contracts import (
    MessagePreprocessInputSchema,
)
from src.modules.preprocessing import TextPreprocessor


def test_text_preprocessor_builds_stable_message_context() -> None:
    created_at = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)
    author_created_at = datetime(2026, 6, 26, 12, 0, tzinfo=timezone.utc)
    member_joined_at = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    raw_text = "ПРИВЕЕЕЕТ\u200b   WORLD!!! https://bit.ly/test discord.gg/AbC123"

    payload = MessagePreprocessInputSchema(
        platform="discord",
        guild_id="100",
        channel_id="200",
        user_id="300",
        message_id="400",
        raw_text=raw_text,
        created_at=created_at,
        author_created_at=author_created_at,
        member_joined_at=member_joined_at,
        mention_count=2,
        role_mention_count=1,
        channel_mention_count=1,
        has_attachments=True,
        attachment_count=2,
        recent_messages=("old message",),
        metadata={"source": "unit_test"},
    )

    context = asyncio.run(TextPreprocessor().process(payload))

    assert context.platform == "discord"
    assert context.guild_id == "100"
    assert context.channel_id == "200"
    assert context.user_id == "300"
    assert context.message_id == "400"
    assert context.raw_text == raw_text
    assert context.normalized_text == "привеет world!! https://bit.ly/test discord.gg/abc123"
    assert context.text_hash == hashlib.sha256(context.normalized_text.encode("utf-8")).hexdigest()
    assert context.language == "mixed"
    assert context.urls == ("https://bit.ly/test", "discord.gg/AbC123")
    assert context.domains == ("bit.ly", "discord.gg")
    assert context.invites == ("abc123",)
    assert context.has_url is True
    assert context.has_invite is True
    assert context.has_shortener is True
    assert context.has_attachments is True
    assert context.attachment_count == 2
    assert context.account_age_days == 10
    assert context.member_age_days == 5
    assert context.recent_messages == ("old message",)
    assert context.metadata["source"] == "unit_test"
    assert context.metadata["feature_version"] == "text_preprocessor_v1"

    assert context.features is not None
    assert context.features.mention_count == 2
    assert context.features.role_mention_count == 1
    assert context.features.channel_mention_count == 1
    assert context.features.has_zero_width is True
    assert context.features.has_suspicious_unicode is True


def test_text_preprocessor_detects_obfuscated_discord_invite() -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="200",
        user_id="300",
        message_id="400",
        raw_text="join discord[.]gg/Hidden123",
    )

    context = asyncio.run(TextPreprocessor().process(payload))

    assert context.invites == ("hidden123",)
    assert context.has_invite is True
    assert context.features is not None
    assert context.features.invite_count == 1


def test_text_preprocessor_handles_empty_message() -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="200",
        user_id="300",
        message_id="400",
        raw_text="",
    )

    context = asyncio.run(TextPreprocessor().process(payload))

    assert context.normalized_text == ""
    assert len(context.text_hash) == 64
    assert context.language == "unknown"
    assert context.urls == ()
    assert context.domains == ()
    assert context.invites == ()
    assert context.has_url is False
    assert context.has_invite is False
    assert context.account_age_days is None
    assert context.member_age_days is None
    assert context.features is not None
    assert context.features.text_length == 0


def test_text_preprocessor_accepts_custom_shortener_domains() -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="200",
        user_id="300",
        message_id="400",
        raw_text="go https://short.local/a",
    )

    context = asyncio.run(
        TextPreprocessor(shortener_domains={"short.local"}).process(payload)
    )

    assert context.domains == ("short.local",)
    assert context.has_shortener is True
