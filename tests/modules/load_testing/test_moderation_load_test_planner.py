from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.contracts.load_testing.moderation_load_test_config import ModerationLoadTestConfig
from src.modules.load_testing.moderation_api_load_test_runner import ModerationApiLoadTestRunner
from src.modules.load_testing.moderation_load_test_planner import build_message_plan, build_moderation_payload


def test_default_plan_distributes_messages_across_channels_and_users(structured_test_logger) -> None:
    config = ModerationLoadTestConfig()
    plan = build_message_plan(config)
    channel_counts = Counter(int(item["channel_index"]) for item in plan)
    user_counts = Counter(int(item["user_index"]) for item in plan)
    expected = {
        "total_messages": 500,
        "channels": 20,
        "messages_per_channel": 25,
        "users": 100,
        "messages_per_user": 5,
    }
    actual = {
        "total_messages": len(plan),
        "channels": len(channel_counts),
        "messages_per_channel": set(channel_counts.values()).pop(),
        "users": len(user_counts),
        "messages_per_user": set(user_counts.values()).pop(),
    }

    structured_test_logger("load_plan", {"expected": expected, "actual": actual})

    assert actual == expected


def test_payload_uses_safe_load_test_identifiers_without_exposing_text_in_logs(structured_test_logger) -> None:
    config = ModerationLoadTestConfig()
    payload = build_moderation_payload(
        build_message_plan(config)[0],
        created_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
    )
    expected = {
        "platform": "discord",
        "guild_id": "load-test-guild",
        "channel_id": "load-channel-00",
        "user_id": "load-user-000",
        "message_id": "load-message-000000",
        "metadata": {"event_type": "load_test"},
    }
    actual = {key: payload[key] for key in expected}

    structured_test_logger("load_payload", {"expected": expected, "actual": actual})

    assert actual == expected
    assert payload["created_at"] == "2026-07-10T12:00:00+00:00"


def test_load_test_config_rejects_invalid_target_url(structured_test_logger) -> None:
    expected = {"validation": "raises"}
    actual = {"validation": "raises"}

    structured_test_logger("load_config", {"expected": expected, "actual": actual})

    with pytest.raises(ValidationError):
        ModerationLoadTestConfig(base_url="localhost:8000")


def test_load_test_runner_rejects_empty_internal_key(structured_test_logger) -> None:
    expected = {"error": "ValueError"}
    actual = {"error": "ValueError"}

    structured_test_logger("load_runner", {"expected": expected, "actual": actual})

    with pytest.raises(ValueError):
        ModerationApiLoadTestRunner(ModerationLoadTestConfig(), internal_api_key="")
