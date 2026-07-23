from datetime import datetime, timezone

from src.modules.load_testing.synthetic_discord_bot_adapter import SyntheticDiscordBotAdapter
from src.modules.load_testing.synthetic_discord_bot_event import SyntheticDiscordAuthor, SyntheticDiscordMessage


def test_synthetic_discord_bot_adapter_builds_moderation_payload() -> None:
    payload = SyntheticDiscordBotAdapter().build_moderation_payload(
        SyntheticDiscordMessage(
            id="message1",
            guild_id="guild1",
            channel_id="channel1",
            author=SyntheticDiscordAuthor(id="user1"),
            content="<@123456789012345678> <@&223456789012345678> <#323456789012345678> привет",
            created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
            attachment_count=1,
            embed_count=2,
        )
    )

    assert payload["platform"] == "discord"
    assert payload["mention_count"] == 1
    assert payload["role_mention_count"] == 1
    assert payload["channel_mention_count"] == 1
    assert payload["has_attachments"] is True
    assert payload["attachment_count"] == 1
    assert payload["metadata"]["event_type"] == "synthetic_discord_message_create"
    assert payload["metadata"]["embed_count"] == 2


def test_synthetic_discord_bot_adapter_builds_dry_run_action_result() -> None:
    payload = SyntheticDiscordBotAdapter().build_action_result_payload(
        {
            "dataset_event_id": 123,
            "message_id": "message1",
            "decision_action": "WARN",
        },
        dry_run=True,
    )

    assert payload is not None
    assert payload["event_id"] == 123
    assert payload["message_id"] == "message1"
    assert payload["action"] == "WARN"
    assert payload["status"] == "DRY_RUN"
    assert payload["dry_run"] is True


def test_synthetic_discord_bot_adapter_skips_ignore_action_result() -> None:
    payload = SyntheticDiscordBotAdapter().build_action_result_payload(
        {
            "dataset_event_id": 123,
            "message_id": "message1",
            "decision_action": "IGNORE",
        },
        dry_run=True,
    )

    assert payload is None
