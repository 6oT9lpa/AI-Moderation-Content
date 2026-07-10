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
