from __future__ import annotations

from src.modules.load_testing.rabbitmq_moderation_contract import RabbitMqModerationResult, RabbitMqModerationTask


def test_rabbitmq_moderation_task_roundtrip_preserves_payload() -> None:
    task = RabbitMqModerationTask.create(
        run_id="run-1",
        sequence=7,
        moderation_payload={"message_id": "m1", "raw_text": "д о е б а т ь с я"},
    )

    restored = RabbitMqModerationTask.from_bytes(task.to_bytes())

    assert restored.task_id == task.task_id
    assert restored.run_id == "run-1"
    assert restored.sequence == 7
    assert restored.moderation_payload["raw_text"] == "д о е б а т ь с я"


def test_rabbitmq_moderation_result_roundtrip_preserves_batch_metadata() -> None:
    result = RabbitMqModerationResult(
        task_id="task-1",
        run_id="run-1",
        sequence=1,
        ok=True,
        worker_id="worker-1",
        batch_size=32,
        enqueued_at="2026-07-24T00:00:00+00:00",
        started_at="2026-07-24T00:00:01+00:00",
        completed_at="2026-07-24T00:00:02+00:00",
        moderation_response={"risk_score": 52.0, "decision_action": "WARN"},
        action_result_response={"status": "accepted"},
    )

    restored = RabbitMqModerationResult.from_bytes(result.to_bytes())

    assert restored.ok is True
    assert restored.batch_size == 32
    assert restored.moderation_response == {"risk_score": 52.0, "decision_action": "WARN"}
    assert restored.action_result_response == {"status": "accepted"}
