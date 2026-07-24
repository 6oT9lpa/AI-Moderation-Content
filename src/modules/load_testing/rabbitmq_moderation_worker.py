from __future__ import annotations

import asyncio
import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pika

from src.contracts.api.action_result_request_schema import ActionResultRequestSchema
from src.contracts.api.moderation_message_request_schema import ModerationMessageRequestSchema
from src.domain.action.action_execution_status import ActionExecutionStatus
from src.domain.moderation.moderation_action import ModerationAction
from src.infrastructure.api.api_settings import ApiSettings
from src.infrastructure.config.settings import Config
from src.modules.load_testing.rabbitmq_moderation_contract import RabbitMqModerationResult, RabbitMqModerationTask
from src.presentation.api.api_composition_root import ApiCompositionRoot


@dataclass(frozen=True)
class RabbitMqModerationWorkerConfig:
    rabbitmq_url: str
    task_queue: str = "ai_moder.moderation.tasks"
    result_queue: str = "ai_moder.moderation.results"
    batch_size: int = 32
    batch_timeout_ms: int = 50
    prefetch_count: int = 128
    action_dry_run: bool = True
    submit_action_results: bool = True
    worker_id: str = f"{socket.gethostname()}-{os.getpid()}"
    metrics_path: str | None = None


class RabbitMqModerationWorker:
    def __init__(self, config: RabbitMqModerationWorkerConfig) -> None:
        self._config = config

    def run_forever(self) -> None:
        asyncio.run(self._run_forever())

    async def _run_forever(self) -> None:
        app_config = Config()
        api_settings = ApiSettings()
        container = ApiCompositionRoot(app_config.database_url, api_settings).build()
        await container.database.initialize()
        await container.service.initialize_policy_status()

        parameters = pika.URLParameters(self._config.rabbitmq_url)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue=self._config.task_queue, durable=True)
        channel.queue_declare(queue=self._config.result_queue, durable=True)
        channel.basic_qos(prefetch_count=self._config.prefetch_count)

        print(
            "rabbitmq worker ready "
            f"worker_id={self._config.worker_id} batch_size={self._config.batch_size} "
            f"batch_timeout_ms={self._config.batch_timeout_ms}",
            flush=True,
        )

        try:
            while True:
                deliveries = self._collect_batch(channel)
                if not deliveries:
                    await asyncio.sleep(0.01)
                    continue
                await self._process_batch(container.service, channel, deliveries)
        finally:
            await container.database.close()
            connection.close()

    def _collect_batch(self, channel) -> list[tuple[int, RabbitMqModerationTask]]:
        deliveries: list[tuple[int, RabbitMqModerationTask]] = []
        deadline = time.perf_counter() + self._config.batch_timeout_ms / 1_000
        while len(deliveries) < self._config.batch_size:
            method_frame, _, body = channel.basic_get(queue=self._config.task_queue, auto_ack=False)
            if method_frame is not None:
                deliveries.append((method_frame.delivery_tag, RabbitMqModerationTask.from_bytes(body)))
                continue
            if deliveries or time.perf_counter() >= deadline:
                break
            time.sleep(0.005)
        return deliveries

    async def _process_batch(self, service, channel, deliveries: list[tuple[int, RabbitMqModerationTask]]) -> None:
        batch_started_perf = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        tasks = [task for _, task in deliveries]
        try:
            requests = [ModerationMessageRequestSchema(**task.moderation_payload) for task in tasks]
            responses = await service.moderate_batch(requests, correlation_id_prefix=f"rabbitmq-{self._config.worker_id}")
            for task, response in zip(tasks, responses, strict=True):
                action_response = None
                if self._config.submit_action_results:
                    action_response = await self._submit_action_result_if_needed(service, response.model_dump(mode="json"))
                result = RabbitMqModerationResult(
                    task_id=task.task_id,
                    run_id=task.run_id,
                    sequence=task.sequence,
                    ok=True,
                    worker_id=self._config.worker_id,
                    batch_size=len(tasks),
                    enqueued_at=task.enqueued_at,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    moderation_response=response.model_dump(mode="json"),
                    action_result_response=action_response,
                )
                self._publish_result(channel, result)
            for delivery_tag, _ in deliveries:
                channel.basic_ack(delivery_tag=delivery_tag)
            self._write_metric(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "worker_id": self._config.worker_id,
                    "ok": True,
                    "batch_size": len(tasks),
                    "duration_ms": round((time.perf_counter() - batch_started_perf) * 1_000, 3),
                }
            )
        except Exception as exc:
            completed_at = datetime.now(timezone.utc).isoformat()
            for delivery_tag, task in deliveries:
                result = RabbitMqModerationResult(
                    task_id=task.task_id,
                    run_id=task.run_id,
                    sequence=task.sequence,
                    ok=False,
                    worker_id=self._config.worker_id,
                    batch_size=len(tasks),
                    enqueued_at=task.enqueued_at,
                    started_at=started_at,
                    completed_at=completed_at,
                    error_kind=type(exc).__name__,
                    error_message=str(exc)[:512],
                )
                self._publish_result(channel, result)
                channel.basic_ack(delivery_tag=delivery_tag)
            self._write_metric(
                {
                    "timestamp": completed_at,
                    "worker_id": self._config.worker_id,
                    "ok": False,
                    "batch_size": len(tasks),
                    "duration_ms": round((time.perf_counter() - batch_started_perf) * 1_000, 3),
                    "error_kind": type(exc).__name__,
                }
            )

    async def _submit_action_result_if_needed(self, service, moderation_response: dict[str, Any]) -> dict[str, Any] | None:
        action = str(moderation_response.get("decision_action") or "IGNORE")
        if action == "IGNORE":
            return None
        request = ActionResultRequestSchema(
            event_id=moderation_response.get("dataset_event_id"),
            message_id=moderation_response.get("message_id"),
            action=ModerationAction(action),
            status=ActionExecutionStatus.DRY_RUN if self._config.action_dry_run else ActionExecutionStatus.SUCCESS,
            dry_run=self._config.action_dry_run,
            timestamp=datetime.now(timezone.utc),
        )
        ack = await service.submit_action_result(request, correlation_id=f"rabbitmq-action-{self._config.worker_id}")
        return ack.model_dump(mode="json")

    def _publish_result(self, channel, result: RabbitMqModerationResult) -> None:
        channel.basic_publish(
            exchange="",
            routing_key=self._config.result_queue,
            body=result.to_bytes(),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )

    def _write_metric(self, metric: dict[str, Any]) -> None:
        if not self._config.metrics_path:
            return
        with open(self._config.metrics_path, "a", encoding="utf-8") as file:
            file.write(json.dumps(metric, ensure_ascii=False, separators=(",", ":")) + "\n")
