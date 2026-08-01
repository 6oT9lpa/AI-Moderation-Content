import asyncio
from types import SimpleNamespace

import pytest

from src.application.moderation_request_queue import ModerationRequestQueue


class _FlakyService:
    def __init__(self, fail_count: int = 0) -> None:
        self.calls = 0
        self.fail_count = fail_count

    async def moderate(self, request, correlation_id, *, persist=True):
        self.calls += 1
        if self.calls <= self.fail_count:
            raise RuntimeError("temporary")
        return correlation_id


@pytest.mark.asyncio
async def test_request_queue_retries_transient_failure() -> None:
    service = _FlakyService(fail_count=2)
    queue = ModerationRequestQueue(service, 1, 10, retry_backoff_seconds=0)
    await queue.start()

    result = await queue.moderate(SimpleNamespace(message_id="1"), "correlation")
    await queue.stop()

    assert result == "correlation"
    assert service.calls == 3


@pytest.mark.asyncio
async def test_request_queue_drains_before_shutdown() -> None:
    completed = asyncio.Event()

    class _SlowService(_FlakyService):
        async def moderate(self, request, correlation_id, *, persist=True):
            await asyncio.sleep(0.01)
            completed.set()
            return correlation_id

    queue = ModerationRequestQueue(_SlowService(), 1, 10)
    await queue.start()
    pending = asyncio.create_task(
        queue.moderate(SimpleNamespace(message_id="1"), "correlation")
    )
    await asyncio.sleep(0)
    await queue.stop()

    assert await pending == "correlation"
    assert completed.is_set()
    with pytest.raises(RuntimeError, match="not accepting"):
        await queue.moderate(SimpleNamespace(message_id="2"), "late")
