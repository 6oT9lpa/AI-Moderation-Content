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
