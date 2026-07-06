from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.infrastructure.logging import get_logger

logger = get_logger("tests.preprocessing")


def test_message_preprocess_input_schema_accepts_minimal_payload() -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
    )

    logger.info(
        "Schema minimal payload created platform=%s guild_id=%s channel_id=%s message_id=%s",
        payload.platform,
        payload.guild_id,
        payload.channel_id,
        payload.message_id,
    )

    assert payload.platform == "discord"
    assert payload.guild_id == "0"
    assert payload.raw_text == ""
    assert payload.mention_count == 0
    assert payload.role_mention_count == 0
    assert payload.channel_mention_count == 0
    assert payload.attachment_count == 0
    assert payload.recent_messages == ()


def test_message_preprocess_input_schema_accepts_full_payload() -> None:
    created_at = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
    author_created_at = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    member_joined_at = datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc)

    payload = MessagePreprocessInputSchema(
        platform="discord",
        guild_id="guild-1",
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="Hello discord.gg/Test123",
        created_at=created_at,
        author_created_at=author_created_at,
        member_joined_at=member_joined_at,
        reply_to_message_id="reply-1",
        mention_count=2,
        role_mention_count=1,
        channel_mention_count=1,
        has_attachments=True,
        attachment_count=2,
        recent_messages=("one", "two"),
        metadata={"source": "unit_test"},
    )

    logger.info(
        "Schema full payload created text_length=%s mentions=%s attachments=%s",
        len(payload.raw_text),
        payload.mention_count,
        payload.attachment_count,
    )

    assert payload.guild_id == "guild-1"
    assert payload.raw_text == "Hello discord.gg/Test123"
    assert payload.has_attachments is True
    assert payload.attachment_count == 2
    assert payload.metadata == {"source": "unit_test"}


@pytest.mark.parametrize(
    "field_name",
    [
        "mention_count",
        "role_mention_count",
        "channel_mention_count",
        "attachment_count",
    ],
)
def test_message_preprocess_input_schema_rejects_negative_counts(field_name: str) -> None:
    data = {
        "channel_id": "channel-1",
        "user_id": "user-1",
        "message_id": "message-1",
        field_name: -1,
    }

    logger.info("Schema negative count validation field=%s", field_name)

    with pytest.raises(ValidationError):
        MessagePreprocessInputSchema(**data)


def test_message_preprocess_input_schema_is_frozen() -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="original",
    )

    logger.info("Schema frozen validation message_id=%s", payload.message_id)

    with pytest.raises(ValidationError):
        payload.raw_text = "changed"  # type: ignore[misc]
