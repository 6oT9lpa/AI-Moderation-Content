from __future__ import annotations

import asyncio
import inspect
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Awaitable, Callable

from src.infrastructure.logging import get_logger
from src.infrastructure.queue.moderation_queue import ModerationQueue
from src.infrastructure.queue.moderation_task import ModerationTask

logger = get_logger(__name__)

TaskHandler = Callable[[ModerationTask], Awaitable[None] | None]


class QueueWorker:
    def __init__(
        self,
        queue: ModerationQueue,
        handler: TaskHandler,
        *,
        worker_count: int = 4,
        thread_count: int | None = None,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 0.05,
    ) -> None:
        if worker_count <= 0:
            raise ValueError("worker_count must be greater than 0")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be greater than 0")

        self._queue = queue
        self._handler = handler
        self._worker_count = worker_count
        self._executor = ThreadPoolExecutor(max_workers=thread_count or worker_count)
        self._tasks: list[asyncio.Task[None]] = []
        self._stopping = asyncio.Event()
        self._max_attempts = max_attempts
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)

        logger.info(
            "Queue worker initialized worker_count=%s thread_count=%s",
            worker_count,
            thread_count or worker_count,
        )

    async def start(self) -> None:
        if self._tasks:
            logger.warning("Queue worker start skipped reason=already_started")
            return

        self._stopping.clear()
        self._tasks = [
            asyncio.create_task(
                self._run_worker(worker_index), name=f"moderation-worker-{worker_index}"
            )
            for worker_index in range(self._worker_count)
        ]
        logger.info("Queue worker pool started worker_count=%s", self._worker_count)

    async def stop(
        self, *, drain: bool = True, drain_timeout_seconds: float = 30.0
    ) -> None:
        logger.info("Queue worker stop requested active_workers=%s", len(self._tasks))
        self._queue.close()
        if drain and self._tasks:
            try:
                await asyncio.wait_for(
                    self._queue.join(), timeout=drain_timeout_seconds
                )
            except TimeoutError:
                logger.error(
                    "Queue worker drain timed out queue_size=%s", self._queue.size
                )
        self._stopping.set()

        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._executor.shutdown(wait=True, cancel_futures=True)
        logger.info("Queue worker pool stopped")

    async def _run_worker(self, worker_index: int) -> None:
        logger.info("Queue worker loop started worker_index=%s", worker_index)

        while not self._stopping.is_set():
            try:
                task = await self._queue.consume()
                await self._handle_task(worker_index, task)
            except asyncio.CancelledError:
                logger.info("Queue worker loop cancelled worker_index=%s", worker_index)
                raise
            except Exception as exc:
                logger.error(
                    "Queue worker loop error worker_index=%s error=%s",
                    worker_index,
                    exc,
                    exc_info=True,
                )

    async def _handle_task(self, worker_index: int, task: ModerationTask) -> None:
        started_at = perf_counter()
        logger.info(
            "Queue task handling started worker_index=%s correlation_id=%s partition=%s message_id=%s",
            worker_index,
            task.correlation_id,
            task.partition_key,
            task.message_id,
        )

        try:
            if inspect.iscoroutinefunction(self._handler):
                await self._handler(task)
            else:
                # Sync handlers are isolated in the thread pool so platform event loops stay responsive.
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(self._executor, self._handler, task)

            latency_ms = round((perf_counter() - started_at) * 1000)
            logger.info(
                "Queue task handling succeeded worker_index=%s correlation_id=%s latency_ms=%s",
                worker_index,
                task.correlation_id,
                latency_ms,
            )
        except Exception as exc:
            latency_ms = round((perf_counter() - started_at) * 1000)
            logger.error(
                "Queue task handling failed worker_index=%s correlation_id=%s latency_ms=%s error=%s",
                worker_index,
                task.correlation_id,
                latency_ms,
                exc,
                exc_info=True,
            )
            attempted = task.next_attempt()
            if attempted.attempts < self._max_attempts and not self._queue.is_closed:
                if self._retry_backoff_seconds:
                    await asyncio.sleep(self._retry_backoff_seconds)
                await self._queue.publish(attempted)
                logger.warning(
                    "Queue task scheduled for retry correlation_id=%s attempt=%s/%s",
                    task.correlation_id,
                    attempted.attempts + 1,
                    self._max_attempts,
                )
            else:
                self._queue.dead_letter(attempted, exc)
        finally:
            self._queue.task_done()
