from __future__ import annotations

import asyncio
import json
import socket
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.modules.load_testing.synthetic_discord_bot_adapter import SyntheticDiscordBotAdapter
from src.modules.load_testing.synthetic_discord_bot_event import SyntheticDiscordAuthor, SyntheticDiscordMessage

_SCENARIO_TEXTS = (
    "доброе утро, собираемся в голосовом канале",
    "посмотрите новости обновления сервера",
    "<@123456789012345678> блядун",
    "д о е б а т ь с я",
    "discord.gg/example приглашение в другой сервер",
    "получи бонус после регистрации по ссылке https://bonus.example/login",
    "госдума приняла странный закон, обсуждаем спокойно",
    "ненавижу эту группу людей, их надо выгнать",
    "я найду твою семью после игры",
    "18+ контент с обнаженными фото тут",
    "скинь токен аккаунта для проверки подарка",
    "привет, кто сегодня играет вечером?",
)


@dataclass(frozen=True)
class SyntheticDiscordBotLoadTestConfig:
    base_url: str
    total_messages: int
    duration_seconds: float
    channel_count: int
    user_count: int
    max_in_flight: int
    request_timeout_seconds: float
    post_action_results: bool = True
    action_dry_run: bool = True

    @property
    def target_messages_per_second(self) -> float:
        return self.total_messages / self.duration_seconds


class SyntheticDiscordBotLoadTestRunner:
    def __init__(self, config: SyntheticDiscordBotLoadTestConfig, *, internal_api_key: str) -> None:
        if not internal_api_key:
            raise ValueError("internal_api_key must not be empty")
        self._config = config
        self._internal_api_key = internal_api_key
        self._adapter = SyntheticDiscordBotAdapter()
        self._request_semaphore = asyncio.Semaphore(config.max_in_flight)

    async def run(self) -> dict[str, Any]:
        plan = self._build_plan()
        started_at = time.perf_counter()
        results = await asyncio.gather(*(self._handle_message(item, started_at) for item in plan))
        elapsed_seconds = time.perf_counter() - started_at
        return self._build_result(results, elapsed_seconds)

    def _build_plan(self) -> tuple[dict[str, Any], ...]:
        interval_seconds = self._config.duration_seconds / self._config.total_messages
        recent_by_user: dict[str, deque[tuple[str, datetime]]] = defaultdict(lambda: deque(maxlen=5))
        plan: list[dict[str, Any]] = []

        for sequence in range(self._config.total_messages):
            created_at = datetime.now(timezone.utc)
            user_id = f"bot-load-user-{sequence % self._config.user_count:05d}"
            content = _SCENARIO_TEXTS[sequence % len(_SCENARIO_TEXTS)]
            recent_items = tuple(recent_by_user[user_id])
            recent_by_user[user_id].append((content, created_at))

            plan.append(
                {
                    "sequence": sequence,
                    "scheduled_offset_seconds": sequence * interval_seconds,
                    "message": SyntheticDiscordMessage(
                        id=f"bot-load-message-{sequence:08d}",
                        guild_id="bot-load-guild",
                        channel_id=f"bot-load-channel-{sequence % self._config.channel_count:04d}",
                        author=SyntheticDiscordAuthor(id=user_id),
                        content=content,
                        created_at=created_at,
                        attachment_count=1 if sequence % 37 == 0 else 0,
                        embed_count=1 if sequence % 41 == 0 else 0,
                    ),
                    "recent_messages": tuple(item[0] for item in recent_items),
                    "recent_message_timestamps": tuple(item[1] for item in recent_items),
                }
            )

        return tuple(plan)

    async def _handle_message(self, plan_item: dict[str, Any], started_at: float) -> dict[str, Any]:
        scheduled_at = started_at + float(plan_item["scheduled_offset_seconds"])
        await asyncio.sleep(max(0.0, scheduled_at - time.perf_counter()))

        message_started_at = time.perf_counter()
        async with self._request_semaphore:
            moderation_started_at = time.perf_counter()
            moderation_status, moderation_error, moderation_response = await asyncio.to_thread(
                self._post_json,
                "/moderation/messages",
                self._adapter.build_moderation_payload(
                    plan_item["message"],
                    recent_messages=plan_item["recent_messages"],
                    recent_message_timestamps=plan_item["recent_message_timestamps"],
                ),
                f"bot-load-{plan_item['sequence']}",
            )
            moderation_latency_ms = (time.perf_counter() - moderation_started_at) * 1_000

            action_status: int | None = None
            action_error: str | None = None
            action_latency_ms = 0.0
            if (
                self._config.post_action_results
                and moderation_response
                and 200 <= int(moderation_status or 0) < 300
            ):
                action_payload = self._adapter.build_action_result_payload(
                    moderation_response,
                    dry_run=self._config.action_dry_run,
                )
                if action_payload is not None:
                    action_started_at = time.perf_counter()
                    action_status, action_error, _ = await asyncio.to_thread(
                        self._post_json,
                        "/actions/result",
                        action_payload,
                        f"bot-load-action-{plan_item['sequence']}",
                    )
                    action_latency_ms = (time.perf_counter() - action_started_at) * 1_000

        return {
            "moderation_status_code": moderation_status,
            "moderation_error_kind": moderation_error,
            "moderation_latency_ms": moderation_latency_ms,
            "action_status_code": action_status,
            "action_error_kind": action_error,
            "action_latency_ms": action_latency_ms,
            "full_latency_ms": (time.perf_counter() - message_started_at) * 1_000,
        }

    def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        correlation_id: str,
    ) -> tuple[int | None, str | None, dict[str, Any] | None]:
        request = urllib.request.Request(
            f"{self._config.base_url.rstrip('/')}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Internal-Api-Key": self._internal_api_key,
                "X-Correlation-Id": correlation_id,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._config.request_timeout_seconds) as response:
                body = response.read()
                data = json.loads(body.decode("utf-8")) if body else None
                return response.status, None, data
        except urllib.error.HTTPError as exc:
            return exc.code, "http_error", None
        except (TimeoutError, socket.timeout):
            return None, "timeout", None
        except urllib.error.URLError:
            return None, "connection_error", None

    def _build_result(self, request_results: list[dict[str, Any]], elapsed_seconds: float) -> dict[str, Any]:
        total = len(request_results)
        moderation_success = sum(
            200 <= int(item["moderation_status_code"]) < 300
            for item in request_results
            if item["moderation_status_code"] is not None
        )
        action_attempts = sum(item["action_status_code"] is not None for item in request_results)
        action_success = sum(
            200 <= int(item["action_status_code"]) < 300
            for item in request_results
            if item["action_status_code"] is not None
        )
        moderation_latencies = sorted(float(item["moderation_latency_ms"]) for item in request_results)
        full_latencies = sorted(float(item["full_latency_ms"]) for item in request_results)
        action_latencies = sorted(float(item["action_latency_ms"]) for item in request_results if item["action_status_code"] is not None)
        status_counts = Counter(str(item["moderation_status_code"]) for item in request_results if item["moderation_status_code"] is not None)
        action_status_counts = Counter(str(item["action_status_code"]) for item in request_results if item["action_status_code"] is not None)
        error_counts = Counter(str(item["moderation_error_kind"]) for item in request_results if item["moderation_error_kind"])
        action_error_counts = Counter(str(item["action_error_kind"]) for item in request_results if item["action_error_kind"])

        return {
            "total_messages": total,
            "moderation_succeeded": moderation_success,
            "moderation_failed": total - moderation_success,
            "moderation_success_rate": round(moderation_success / total if total else 0.0, 6),
            "action_result_attempts": action_attempts,
            "action_result_succeeded": action_success,
            "action_result_failed": action_attempts - action_success,
            "elapsed_seconds": round(elapsed_seconds, 3),
            "achieved_messages_per_second": round(total / elapsed_seconds, 3) if elapsed_seconds else 0.0,
            "moderation_latency": self._latency_summary(moderation_latencies),
            "full_bot_latency": self._latency_summary(full_latencies),
            "action_result_latency": self._latency_summary(action_latencies),
            "moderation_status_counts": dict(sorted(status_counts.items())),
            "action_status_counts": dict(sorted(action_status_counts.items())),
            "moderation_error_counts": dict(sorted(error_counts.items())),
            "action_error_counts": dict(sorted(action_error_counts.items())),
            "targets_met": moderation_success == total and action_success == action_attempts,
        }

    @staticmethod
    def _latency_summary(values: list[float]) -> dict[str, float]:
        if not values:
            return {"mean_ms": 0.0, "p50_ms": 0.0, "p80_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}
        return {
            "mean_ms": round(sum(values) / len(values), 3),
            "p50_ms": round(_percentile(values, 0.50), 3),
            "p80_ms": round(_percentile(values, 0.80), 3),
            "p95_ms": round(_percentile(values, 0.95), 3),
            "p99_ms": round(_percentile(values, 0.99), 3),
        }


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    index = (len(values) - 1) * quantile
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)
