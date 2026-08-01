import asyncio

from src.application.api_moderation_service import ApiModerationService
from src.application.moderation_queue_item import ModerationQueueItem
from src.contracts.api.moderation_message_request_schema import (
    ModerationMessageRequestSchema,
)
from src.contracts.api.moderation_message_response_schema import (
    ModerationMessageResponseSchema,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ModerationRequestQueue:
    def __init__(
        self,
        service: ApiModerationService,
        worker_count: int,
        max_size: int,
        *,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 0.05,
    ) -> None:
        self._service = service
        self._worker_count = worker_count
        self._queue: asyncio.Queue[ModerationQueueItem] = asyncio.Queue(
            maxsize=max_size
        )
        self._workers: list[asyncio.Task[None]] = []
        self._accepting = False
        self._max_attempts = max(1, max_attempts)
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    async def start(self) -> None:
        if self._workers:
            return
        self._accepting = True
        self._workers = [
            asyncio.create_task(self._worker(index), name=f"moderation-api-{index}")
            for index in range(self._worker_count)
        ]

    async def stop(self, *, drain_timeout_seconds: float = 30.0) -> None:
        self._accepting = False
        try:
            await asyncio.wait_for(self._queue.join(), timeout=drain_timeout_seconds)
        except TimeoutError:
            logger.error(
                "Moderation request queue drain timed out pending=%s",
                self._queue.qsize(),
            )
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def moderate(
        self,
        request: ModerationMessageRequestSchema,
        correlation_id: str,
        *,
        persist: bool = True,
    ) -> ModerationMessageResponseSchema:
        if not self._accepting:
            raise RuntimeError("moderation queue is not accepting requests")
        if self._queue.full():
            raise RuntimeError("moderation queue is full")
        future: asyncio.Future[ModerationMessageResponseSchema] = (
            asyncio.get_running_loop().create_future()
        )
        self._queue.put_nowait(
            ModerationQueueItem(request, correlation_id, future, persist)
        )
        return await future

    async def _worker(self, worker_id: int) -> None:
        while True:
            item = await self._queue.get()
            try:
                result = await self._moderate_with_retry(item, worker_id)
                if not item.future.done():
                    item.future.set_result(result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "Moderation queue item failed worker=%s message_id=%s error=%s",
                    worker_id,
                    item.request.message_id,
                    type(exc).__name__,
                )
                if not item.future.done():
                    item.future.set_exception(exc)
            finally:
                self._queue.task_done()

    async def _moderate_with_retry(
        self, item: ModerationQueueItem, worker_id: int
    ) -> ModerationMessageResponseSchema:
        for attempt in range(1, self._max_attempts + 1):
            try:
                return await self._service.moderate(
                    item.request, item.correlation_id, persist=item.persist
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                if attempt == self._max_attempts:
                    raise
                logger.warning(
                    "Moderation queue item retry worker=%s message_id=%s attempt=%s/%s",
                    worker_id,
                    item.request.message_id,
                    attempt + 1,
                    self._max_attempts,
                )
                if self._retry_backoff_seconds:
                    await asyncio.sleep(self._retry_backoff_seconds)
        raise AssertionError("unreachable")
