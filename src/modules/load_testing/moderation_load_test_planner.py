from __future__ import annotations

from datetime import datetime
from typing import Any

from src.contracts.load_testing.moderation_load_test_config import ModerationLoadTestConfig

_SCENARIO_TEXTS = (
    "доброе утро, собираемся в голосовом канале",
    "прикрепил документацию к проекту",
    "посмотрите новости обновления сервера",
    "discord.gg/example приглашение в другой сервер",
    "получи бонус после регистрации по ссылке",
    "пожалуйста, не отправляй сообщения подряд",
    "ссылка на официальный сайт проекта",
    "обсудим расписание матчей вечером",
)


def build_message_plan(config: ModerationLoadTestConfig) -> tuple[dict[str, int | float], ...]:
    interval_seconds = config.duration_seconds / config.total_messages
    return tuple(
        {
            "sequence": sequence,
            "channel_index": sequence % config.channel_count,
            "user_index": sequence % config.user_count,
            "scenario_index": sequence % len(_SCENARIO_TEXTS),
            "scheduled_offset_seconds": sequence * interval_seconds,
        }
        for sequence in range(config.total_messages)
    )


def build_moderation_payload(
    plan_item: dict[str, int | float],
    *,
    created_at: datetime,
) -> dict[str, Any]:
    sequence = int(plan_item["sequence"])
    return {
        "platform": "discord",
        "guild_id": "load-test-guild",
        "channel_id": f"load-channel-{int(plan_item['channel_index']):02d}",
        "user_id": f"load-user-{int(plan_item['user_index']):03d}",
        "message_id": f"load-message-{sequence:06d}",
        "raw_text": _SCENARIO_TEXTS[int(plan_item["scenario_index"])],
        "created_at": created_at.isoformat(),
        "metadata": {"event_type": "load_test"},
    }
