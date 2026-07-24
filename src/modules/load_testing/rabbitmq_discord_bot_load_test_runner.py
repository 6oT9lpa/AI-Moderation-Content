from __future__ import annotations

import asyncio
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pika

from src.modules.load_testing.rabbitmq_moderation_contract import RabbitMqModerationResult, RabbitMqModerationTask
from src.modules.load_testing.synthetic_discord_bot_adapter import SyntheticDiscordBotAdapter
from src.modules.load_testing.synthetic_discord_bot_event import SyntheticDiscordAuthor, SyntheticDiscordMessage

SCENARIO_TEXTS = (
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
class RabbitMqDiscordBotLoadTestConfig:
    rabbitmq_url: str
    task_queue: str
    result_queue: str
    total_messages: int
    duration_seconds: float
    channel_count: int
    user_count: int
    publish_timeout_seconds: float = 10.0
    result_timeout_seconds: float = 120.0

    @property
    def target_messages_per_second(self) -> float:
        return self.total_messages / self.duration_seconds


class RabbitMqDiscordBotLoadTestRunner:
    def __init__(self, config: RabbitMqDiscordBotLoadTestConfig) -> None:
        self._config = config
        self._adapter = SyntheticDiscordBotAdapter()
        self._run_id = uuid4().hex[:12]

    async def run(self) -> dict[str, Any]:
        started_at = time.perf_counter()
        payloads = self._build_payloads()
        tasks = await asyncio.to_thread(self._publish_tasks, payloads, started_at)
        publish_elapsed = time.perf_counter() - started_at
        results = await asyncio.to_thread(self._collect_results, len(tasks))
        elapsed_seconds = time.perf_counter() - started_at
        return self._build_result(tasks, results, publish_elapsed, elapsed_seconds)

    def _build_payloads(self) -> tuple[dict[str, Any], ...]:
        recent_by_user: dict[str, deque[tuple[str, datetime]]] = defaultdict(lambda: deque(maxlen=5))
        payloads: list[dict[str, Any]] = []

        for sequence in range(self._config.total_messages):
            created_at = datetime.now(timezone.utc)
            user_id = f"rabbitmq-user-{sequence % self._config.user_count:05d}"
            content = SCENARIO_TEXTS[sequence % len(SCENARIO_TEXTS)]
            recent_items = tuple(recent_by_user[user_id])
            recent_by_user[user_id].append((content, created_at))
            message = SyntheticDiscordMessage(
                id=f"rabbitmq-message-{self._run_id}-{sequence:08d}",
                guild_id="rabbitmq-load-guild",
                channel_id=f"rabbitmq-load-channel-{sequence % self._config.channel_count:04d}",
                author=SyntheticDiscordAuthor(id=user_id),
                content=content,
                created_at=created_at,
                attachment_count=1 if sequence % 37 == 0 else 0,
                embed_count=1 if sequence % 41 == 0 else 0,
            )
            payloads.append(
                self._adapter.build_moderation_payload(
                    message,
                    recent_messages=tuple(item[0] for item in recent_items),
                    recent_message_timestamps=tuple(item[1] for item in recent_items),
                )
            )

        return tuple(payloads)

    def _connection(self) -> pika.BlockingConnection:
        return pika.BlockingConnection(pika.URLParameters(self._config.rabbitmq_url))

    def _publish_tasks(self, payloads: tuple[dict[str, Any], ...], started_at: float) -> tuple[RabbitMqModerationTask, ...]:
        tasks: list[RabbitMqModerationTask] = []
        connection = self._connection()
        try:
            channel = connection.channel()
            channel.queue_declare(queue=self._config.task_queue, durable=True)
            channel.queue_declare(queue=self._config.result_queue, durable=True)
            for sequence, payload in enumerate(payloads):
                interval_seconds = self._config.duration_seconds / self._config.total_messages
                scheduled_at = started_at + sequence * interval_seconds
                sleep_for = scheduled_at - time.perf_counter()
                if sleep_for > 0:
                    time.sleep(sleep_for)
                task = RabbitMqModerationTask.create(run_id=self._run_id, sequence=sequence, moderation_payload=payload)
                tasks.append(task)
                channel.basic_publish(
                    exchange="",
                    routing_key=self._config.task_queue,
                    body=task.to_bytes(),
                    properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
                )
        finally:
            connection.close()
        return tuple(tasks)

    def _collect_results(self, expected_count: int) -> list[RabbitMqModerationResult]:
        deadline = time.perf_counter() + self._config.result_timeout_seconds
        results: list[RabbitMqModerationResult] = []
        connection = self._connection()
        try:
            channel = connection.channel()
            channel.queue_declare(queue=self._config.result_queue, durable=True)
            while len(results) < expected_count and time.perf_counter() < deadline:
                method_frame, _, body = channel.basic_get(queue=self._config.result_queue, auto_ack=False)
                if method_frame is None:
                    time.sleep(0.02)
                    continue
                result = RabbitMqModerationResult.from_bytes(body)
                if result.run_id == self._run_id:
                    results.append(result)
                channel.basic_ack(delivery_tag=method_frame.delivery_tag)
        finally:
            connection.close()
        return results

    def _build_result(
        self,
        tasks: tuple[RabbitMqModerationTask, ...],
        results: list[RabbitMqModerationResult],
        publish_elapsed: float,
        elapsed_seconds: float,
    ) -> dict[str, Any]:
        by_task_id = {result.task_id: result for result in results}
        ok_results = [result for result in results if result.ok]
        end_to_end_latencies = sorted(
            (_parse_ts(result.completed_at) - _parse_ts(result.enqueued_at)) * 1_000
            for result in results
        )
        moderation_latencies = sorted(
            float(result.moderation_response.get("latency_ms", 0))
            for result in ok_results
            if result.moderation_response is not None
        )
        action_attempts = sum(result.action_result_response is not None for result in ok_results)
        worker_counts = Counter(result.worker_id for result in results)
        batch_sizes = sorted(result.batch_size for result in ok_results)
        missing = len(tasks) - len(by_task_id)
        return {
            "run_id": self._run_id,
            "total_messages": len(tasks),
            "results_received": len(results),
            "missing_results": missing,
            "moderation_succeeded": len(ok_results),
            "moderation_failed": len(results) - len(ok_results) + missing,
            "moderation_success_rate": round(len(ok_results) / len(tasks), 6) if tasks else 0.0,
            "publish_elapsed_seconds": round(publish_elapsed, 3),
            "elapsed_seconds": round(elapsed_seconds, 3),
            "achieved_publish_messages_per_second": round(len(tasks) / publish_elapsed, 3) if publish_elapsed else 0.0,
            "achieved_end_to_end_messages_per_second": round(len(ok_results) / elapsed_seconds, 3) if elapsed_seconds else 0.0,
            "end_to_end_latency": _latency_summary(end_to_end_latencies),
            "moderation_latency": _latency_summary(moderation_latencies),
            "action_result_attempts": action_attempts,
            "worker_counts": dict(sorted(worker_counts.items())),
            "batch_size": {
                "mean": round(sum(batch_sizes) / len(batch_sizes), 3) if batch_sizes else 0.0,
                "p50": round(_percentile(batch_sizes, 0.5), 3) if batch_sizes else 0.0,
                "p80": round(_percentile(batch_sizes, 0.8), 3) if batch_sizes else 0.0,
            },
            "error_counts": dict(sorted(Counter(result.error_kind for result in results if result.error_kind).items())),
            "targets_met": len(ok_results) == len(tasks),
        }


def _parse_ts(value: str) -> float:
    return datetime.fromisoformat(value).timestamp()


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


def _percentile(values: list[float] | list[int], quantile: float) -> float:
    if not values:
        return 0.0
    index = (len(values) - 1) * quantile
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    return float(values[lower] + (values[upper] - values[lower]) * (index - lower))
