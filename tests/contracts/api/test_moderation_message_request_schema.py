from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.contracts.api.moderation_message_request_schema import ModerationMessageRequestSchema
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


def _payload() -> dict[str, object]:
    return {
        "guild_id": "1",
        "channel_id": "2",
        "user_id": "3",
        "message_id": "4",
        "raw_text": "secret test message",
        "created_at": datetime.now(timezone.utc),
    }


def test_schema_accepts_strict_valid_payload() -> None:
    logger.info("Schema test expected=valid actual=valid request shape")
    schema = ModerationMessageRequestSchema(**_payload())
    assert schema.message_id == "4"


def test_schema_rejects_unknown_and_oversized_values() -> None:
    logger.info("Schema test expected=ValidationError actual=unknown and oversized fields")
    unknown = _payload()
    unknown["unknown"] = True
    with pytest.raises(ValidationError):
        ModerationMessageRequestSchema(**unknown)
    oversized = _payload()
    oversized["raw_text"] = "x" * 8_001
    with pytest.raises(ValidationError):
        ModerationMessageRequestSchema(**oversized)


def test_schema_accepts_user_moderation_context_and_update_event() -> None:
    payload = _payload()
    payload["event_type"] = "UPDATE"
    payload["user_context"] = {
        "account_created_at": "2024-01-01T00:00:00+00:00",
        "joined_guild_at": "2025-01-01T00:00:00+00:00",
        "account_age_days": 100,
        "guild_membership_days": 30,
        "punishments": {"window_days": 30, "total_in_window": 2, "timeouts_in_window": 1, "ai_deleted_messages_in_window": 1, "bans_in_window": 0, "last_punishment_at": "2026-01-01T00:00:00+00:00"},
    }
    schema = ModerationMessageRequestSchema(**payload)
    assert schema.event_type == "UPDATE"
    assert schema.user_context.punishments.total_in_window == 2


def test_schema_accepts_flattened_reply_context_metadata() -> None:
    """Discord reply context must use scalars because API metadata is safe-by-design."""
    payload = _payload()
    payload["metadata"] = {
        "reply_context_message_id": "123",
        "reply_context_author_id": "456",
        "reply_context_text": "The message being answered.",
    }

    schema = ModerationMessageRequestSchema(**payload)

    assert schema.metadata["reply_context_message_id"] == "123"
    payload["metadata"] = {"reply_context": {"message_id": "123"}}
    with pytest.raises(ValidationError):
        ModerationMessageRequestSchema(**payload)
