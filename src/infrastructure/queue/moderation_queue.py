from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count

from src.infrastructure.logging import get_logger
from src.infrastructure.queue.moderation_task import ModerationTask

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DeadLetter:
    task: ModerationTask
    error_type: str
    error_message: str
    failed_at: datetime


class ModerationQueue:
    def __init__(
        self, *, max_size: int = 10000, max_payload_bytes: int = 65_536
    ) -> None:
        if max_payload_bytes <= 0:
            raise ValueError("max_payload_bytes must be greater than zero")
        self._queue: asyncio.PriorityQueue[tuple[int, int, ModerationTask]] = (
            asyncio.PriorityQueue(
                maxsize=max_size,
            )
        )
        self._sequence = count()
        self._closed = False
        self._dead_letters: list[DeadLetter] = []
        self._max_payload_bytes = max_payload_bytes
        logger.info("Moderation queue initialized max_size=%s", max_size)

    async def publish(self, task: ModerationTask) -> None:
        if self._closed:
            logger.error(
                "Moderation task publish rejected queue_closed=true correlation_id=%s message_id=%s",
                task.correlation_id,
                task.message_id,
            )
            raise RuntimeError("moderation queue is closed")

        if self._payload_size(task.payload) > self._max_payload_bytes:
            raise ValueError("moderation task payload exceeds maximum size")

        await self._queue.put((task.priority, next(self._sequence), task))
        logger.info(
            "Moderation task published correlation_id=%s platform=%s partition=%s message_id=%s queue_size=%s",
            task.correlation_id,
            task.source_platform,
            task.partition_key,
            task.message_id,
            self.size,
        )

    async def consume(self) -> ModerationTask:
        _priority, _sequence_number, task = await self._queue.get()
        logger.info(
            "Moderation task consumed correlation_id=%s partition=%s message_id=%s queue_size=%s",
            task.correlation_id,
            task.partition_key,
            task.message_id,
            self.size,
        )
        return task

    def task_done(self) -> None:
        self._queue.task_done()
        logger.debug("Moderation task marked done queue_size=%s", self.size)

    async def join(self) -> None:
        logger.info("Moderation queue join started queue_size=%s", self.size)
        await self._queue.join()
        logger.info("Moderation queue join finished")

    def close(self) -> None:
        self._closed = True
        logger.info("Moderation queue closed queue_size=%s", self.size)

    def dead_letter(self, task: ModerationTask, error: Exception) -> None:
        self._dead_letters.append(
            DeadLetter(
                task=task,
                error_type=type(error).__name__,
                error_message=str(error)[:512],
                failed_at=datetime.now(timezone.utc),
            )
        )
        logger.error(
            "Moderation task moved to dead letter correlation_id=%s attempts=%s error_type=%s",
            task.correlation_id,
            task.attempts,
            type(error).__name__,
        )

    @property
    def dead_letters(self) -> tuple[DeadLetter, ...]:
        return tuple(self._dead_letters)

    @property
    def size(self) -> int:
        return self._queue.qsize()

    @property
    def is_closed(self) -> bool:
        return self._closed

    @staticmethod
    def _payload_size(payload: object) -> int:
        try:
            return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError("moderation task payload must be serializable") from exc
