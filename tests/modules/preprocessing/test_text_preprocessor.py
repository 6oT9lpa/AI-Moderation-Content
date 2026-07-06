from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.infrastructure.logging import get_logger
from src.modules.preprocessing.text_preprocessor import TextPreprocessor

logger = get_logger("tests.preprocessing")


@pytest.mark.asyncio
async def test_text_preprocessor_builds_message_context() -> None:
    created_at = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
    author_created_at = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    member_joined_at = datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc)

    payload = MessagePreprocessInputSchema(
        platform="discord",
        guild_id="guild-1",
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="HELLO   привет https://discord.gg/Test123 😀",
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

    context = await TextPreprocessor().process(payload)

    logger.info(
        "Preprocessor context built message_id=%s language=%s urls=%s domains=%s invites=%s features=%s",
        context.message_id,
        context.language,
        context.urls,
        context.domains,
        context.invites,
        context.features.to_dict() if context.features else None,
    )

    assert context.platform == "discord"
    assert context.guild_id == "guild-1"
    assert context.channel_id == "channel-1"
    assert context.user_id == "user-1"
    assert context.message_id == "message-1"
    assert context.raw_text == payload.raw_text
    assert context.normalized_text == "hello привет https://discord.gg/test123 😀"
    assert len(context.text_hash) == 64
    assert context.language == "mixed"
    assert context.urls == ("https://discord.gg/Test123",)
    assert context.domains == ("discord.gg",)
    assert context.invites == ("test123",)
    assert context.has_url is True
    assert context.has_invite is True
    assert context.has_attachments is True
    assert context.attachment_count == 2
    assert context.account_age_days == 6
    assert context.member_age_days == 4
    assert context.recent_messages == ("old message",)
    assert context.metadata["source"] == "unit_test"
    assert context.metadata["feature_version"] == "text_preprocessor_v1"
    assert context.features is not None
    assert context.features.mention_count == 2
    assert context.features.role_mention_count == 1
    assert context.features.channel_mention_count == 1


@pytest.mark.asyncio
async def test_text_preprocessor_hash_is_deterministic_for_normalized_text() -> None:
    payload_one = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="HELLO    WORLD",
    )
    payload_two = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-2",
        raw_text="hello world",
    )

    preprocessor = TextPreprocessor()
    context_one = await preprocessor.process(payload_one)
    context_two = await preprocessor.process(payload_two)

    logger.info(
        "Preprocessor deterministic hash hash_one=%s hash_two=%s normalized_one=%r normalized_two=%r",
        context_one.text_hash,
        context_two.text_hash,
        context_one.normalized_text,
        context_two.normalized_text,
    )

    assert context_one.normalized_text == context_two.normalized_text
    assert context_one.text_hash == context_two.text_hash


@pytest.mark.asyncio
async def test_text_preprocessor_detects_shortener_domain() -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="click bit.ly/scam",
    )

    context = await TextPreprocessor().process(payload)

    logger.info(
        "Preprocessor shortener detection domains=%s has_shortener=%s",
        context.domains,
        context.has_shortener,
    )

    assert context.domains == ("bit.ly",)
    assert context.has_shortener is True
    assert context.features is not None
    assert context.features.has_shortener is True


@pytest.mark.asyncio
async def test_text_preprocessor_detects_unknown_language_for_empty_text() -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="",
    )

    context = await TextPreprocessor().process(payload)

    logger.info("Preprocessor empty text language=%s features=%s", context.language, context.features)

    assert context.normalized_text == ""
    assert context.language == "unknown"
    assert context.urls == ()
    assert context.domains == ()
    assert context.invites == ()
    assert context.has_url is False
    assert context.has_invite is False
    assert context.features is not None
    assert context.features.text_length == 0
