import asyncio

from src.application.api_moderation_service import ApiModerationService
from src.application.moderation_queue_item import ModerationQueueItem
from src.contracts.api.moderation_message_request_schema import ModerationMessageRequestSchema
from src.contracts.api.moderation_message_response_schema import ModerationMessageResponseSchema
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ModerationRequestQueue:
    def __init__(self, service: ApiModerationService, worker_count: int, max_size: int) -> None:
        self._service = service
        self._worker_count = worker_count
        self._queue: asyncio.Queue[ModerationQueueItem] = asyncio.Queue(maxsize=max_size)
        self._workers: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        if self._workers:
            return
        self._workers = [asyncio.create_task(self._worker(index), name=f"moderation-api-{index}") for index in range(self._worker_count)]

    async def stop(self) -> None:
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def moderate(self, request: ModerationMessageRequestSchema, correlation_id: str) -> ModerationMessageResponseSchema:
        if self._queue.full():
            raise RuntimeError("moderation queue is full")
        future: asyncio.Future[ModerationMessageResponseSchema] = asyncio.get_running_loop().create_future()
        self._queue.put_nowait(ModerationQueueItem(request, correlation_id, future))
        return await future

    async def _worker(self, worker_id: int) -> None:
        while True:
            item = await self._queue.get()
            try:
                result = await self._service.moderate(item.request, item.correlation_id)
                if not item.future.done():
                    item.future.set_result(result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Moderation queue item failed worker=%s message_id=%s error=%s", worker_id, item.request.message_id, type(exc).__name__)
                if not item.future.done():
                    item.future.set_exception(exc)
            finally:
                self._queue.task_done()
