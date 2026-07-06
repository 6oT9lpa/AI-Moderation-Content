from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.contracts import (
    MessagePreprocessInputSchema,
)


def test_message_preprocess_input_accepts_valid_payload() -> None:
    payload = MessagePreprocessInputSchema(
        platform="discord",
        guild_id="100",
        channel_id="200",
        user_id="300",
        message_id="400",
        raw_text="hello",
        created_at=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        mention_count=1,
        role_mention_count=2,
        channel_mention_count=3,
        has_attachments=True,
        attachment_count=1,
        recent_messages=("a", "b"),
        metadata={"author_is_bot": False},
    )

    assert payload.platform == "discord"
    assert payload.guild_id == "100"
    assert payload.mention_count == 1
    assert payload.attachment_count == 1
    assert payload.metadata["author_is_bot"] is False


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("mention_count", -1),
        ("role_mention_count", -1),
        ("channel_mention_count", -1),
        ("attachment_count", -1),
    ],
)

def test_message_preprocess_input_rejects_negative_counters(
    field_name: str,
    field_value: int,
) -> None:
    data = {
        "channel_id": "200",
        "user_id": "300",
        "message_id": "400",
        field_name: field_value,
    }

    with pytest.raises(ValidationError):
        MessagePreprocessInputSchema(**data)


def test_message_preprocess_input_is_frozen() -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="200",
        user_id="300",
        message_id="400",
        raw_text="original",
    )

    with pytest.raises(ValidationError):
        payload.raw_text = "changed"  # type: ignore[misc]
