from __future__ import annotations

import asyncio
from threading import Lock

import pytest

from src.infrastructure.logging import get_logger
from src.infrastructure.queue.moderation_queue import ModerationQueue
from src.infrastructure.queue.moderation_task import ModerationTask
from src.infrastructure.queue.queue_worker import QueueWorker

logger = get_logger("tests.preprocessing")


@pytest.mark.asyncio
async def test_moderation_queue_processes_tasks_with_worker_threads() -> None:
    queue = ModerationQueue(max_size=10)
    processed: list[str] = []
    lock = Lock()

    def handle_task(task: ModerationTask) -> None:
        logger.info(
            "Queue test handler processing correlation_id=%s partition=%s message_id=%s",
            task.correlation_id,
            task.partition_key,
            task.message_id,
        )
        with lock:
            processed.append(task.message_id)

    worker = QueueWorker(queue, handle_task, worker_count=2, thread_count=2)
    await worker.start()

    await queue.publish(
        ModerationTask(
            source_platform="discord",
            space_id="guild-1",
            channel_id="channel-1",
            message_id="message-1",
            payload={"text": "one"},
        ),
    )
    await queue.publish(
        ModerationTask(
            source_platform="telegram",
            space_id="chat-1",
            channel_id="topic-1",
            message_id="message-2",
            payload={"text": "two"},
        ),
    )

    await asyncio.wait_for(queue.join(), timeout=5)
    await worker.stop()

    logger.info("Queue test processed messages=%s", processed)

    assert sorted(processed) == ["message-1", "message-2"]


@pytest.mark.asyncio
async def test_moderation_queue_rejects_oversized_or_non_json_payloads() -> None:
    queue = ModerationQueue(max_payload_bytes=32)

    with pytest.raises(ValueError, match="maximum size"):
        await queue.publish(
            ModerationTask(
                source_platform="discord",
                space_id="guild-1",
                channel_id="channel-1",
                message_id="message-large",
                payload={"text": "x" * 64},
            )
        )

    with pytest.raises(ValueError, match="serializable"):
        await queue.publish(
            ModerationTask(
                source_platform="discord",
                space_id="guild-1",
                channel_id="channel-1",
                message_id="message-object",
                payload={"object": object()},
            )
        )


@pytest.mark.asyncio
async def test_worker_retries_then_dead_letters_failed_task() -> None:
    queue = ModerationQueue(max_size=10)
    handled_attempts: list[int] = []

    async def fail(task: ModerationTask) -> None:
        handled_attempts.append(task.attempts)
        raise RuntimeError("provider unavailable")

    worker = QueueWorker(queue, fail, worker_count=1, max_attempts=3, retry_backoff_seconds=0)
    await worker.start()
    await queue.publish(
        ModerationTask(
            source_platform="discord",
            space_id="guild-1",
            channel_id="channel-1",
            message_id="message-failed",
            payload={"text": "retry me"},
        )
    )

    await asyncio.wait_for(queue.join(), timeout=5)
    await worker.stop()

    assert handled_attempts == [0, 1, 2]
    assert len(queue.dead_letters) == 1
    assert queue.dead_letters[0].task.attempts == 3
    assert queue.dead_letters[0].error_type == "RuntimeError"


@pytest.mark.asyncio
async def test_worker_stop_drains_in_flight_tasks() -> None:
    queue = ModerationQueue(max_size=10)
    completed = asyncio.Event()

    async def handle(_: ModerationTask) -> None:
        await asyncio.sleep(0.01)
        completed.set()

    worker = QueueWorker(queue, handle, worker_count=1)
    await worker.start()
    await queue.publish(
        ModerationTask(
            source_platform="discord",
            space_id="guild-1",
            channel_id="channel-1",
            message_id="message-drain",
            payload={"text": "finish me"},
        )
    )

    await worker.stop(drain=True)

    assert completed.is_set()
    assert queue.size == 0
