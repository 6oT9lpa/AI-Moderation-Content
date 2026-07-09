from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.training.datasets.discord_auto_labeler import DiscordAutoLabeler


def _raw_row(
    message_id: str,
    content: str,
    *,
    user_id: str = "user-1",
    offset_seconds: int = 0,
) -> dict:
    created_at = datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_seconds)
    return {
        "message_id": message_id,
        "content": content,
        "created_at": created_at.isoformat(),
        "guild_id_hash": "guild-hash",
        "channel_id_hash": "channel-hash",
        "user_id_hash": user_id,
        "source_tag": "test_channel",
        "attachments_count": 0,
        "embeds_count": 0,
    }


@pytest.mark.asyncio
async def test_discord_auto_labeler_marks_toxicity_with_local_rules() -> None:
    labeler = DiscordAutoLabeler()

    rows = await labeler.label_raw_rows(
        [
            _raw_row("m1", "\u043e\u0431\u044b\u0447\u043d\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435"),
            _raw_row("m2", "\u0442\u044b \u0438\u0434\u0438\u043e\u0442", offset_seconds=2),
        ]
    )

    toxic_row = rows[1]
    assert toxic_row["primary_label"] == "TOXIC"
    assert "TOXIC" in toxic_row["labels"]
    assert "dataset_silver_toxic" in toxic_row["metadata"]["matched_rules"]
    assert toxic_row["metadata"]["toxicity_gate"] is False


@pytest.mark.asyncio
async def test_discord_auto_labeler_keeps_rule_labels_for_invites_and_flood() -> None:
    labeler = DiscordAutoLabeler()
    rows = [
        _raw_row("invite", "заходи https://discord.gg/testcode", user_id="invite-user"),
        *[
            _raw_row(f"flood-{index}", "одно и то же сообщение", user_id="flood-user", offset_seconds=index)
            for index in range(5)
        ],
    ]

    labeled_rows = await labeler.label_raw_rows(rows)
    invite_row = next(row for row in labeled_rows if row["message_id"] == "invite")
    flood_row = next(row for row in labeled_rows if row["message_id"] == "flood-4")

    assert "INVITE" in invite_row["labels"]
    assert "URL" in invite_row["labels"]
    assert "FLOOD" in flood_row["labels"]
    assert flood_row["primary_label"] == "FLOOD"


@pytest.mark.asyncio
async def test_discord_auto_labeler_adds_semantic_silver_labels() -> None:
    labeler = DiscordAutoLabeler()

    rows = await labeler.label_raw_rows(
        [
            _raw_row("scam", "получи 5000 руб прямо сейчас"),
            _raw_row("ad", "скидка и промокод на магазин"),
        ]
    )

    by_id = {row["message_id"]: row for row in rows}
    assert by_id["scam"]["primary_label"] == "SCAM"
    assert "SCAM" in by_id["scam"]["labels"]
    assert by_id["ad"]["primary_label"] == "ADVERTISEMENT"
    assert by_id["ad"]["feedback_type"] == "silver_auto_labeled"
