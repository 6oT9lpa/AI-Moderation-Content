from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.discord_message_exporter import (
    DiscordChannelExport,
    DiscordMessageConverter,
)


def test_discord_message_converter_builds_safe_project_row() -> None:
    converter = DiscordMessageConverter(hash_salt="test-salt")
    channel = DiscordChannelExport(
        guild_id="guild-1",
        channel_id="channel-1",
        label=ModerationLabel.SAFE,
        source_tag="hard_safe",
    )
    message = {
        "id": "message-1",
        "timestamp": "2026-07-09T00:00:00+00:00",
        "edited_timestamp": None,
        "content": "Документация: https://github.com/example/project user@example.com",
        "author": {"id": "user-1", "bot": False},
        "attachments": [],
        "embeds": [],
    }

    row = converter.to_project_training_row(message, channel)
    raw = converter.to_raw_record(message, channel)

    assert row is not None
    assert row["message_id"] == "message-1"
    assert row["primary_label"] == "SAFE"
    assert row["labels"] == ["SAFE"]
    assert row["feedback_type"] == "confirmed"
    assert "<URL_DOMAIN:github.com>" in row["model_text"]
    assert "<EMAIL>" in row["model_text"]
    assert "user@example.com" not in row["model_text"]
    assert raw["content"].startswith("Документация")
    assert raw["user_id_hash"] == row["metadata"]["user_id_hash"]
