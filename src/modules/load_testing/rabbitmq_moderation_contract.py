from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class RabbitMqModerationTask:
    task_id: str
    run_id: str
    sequence: int
    moderation_payload: dict[str, Any]
    enqueued_at: str

    @classmethod
    def create(cls, *, run_id: str, sequence: int, moderation_payload: dict[str, Any]) -> "RabbitMqModerationTask":
        return cls(
            task_id=f"{run_id}-{sequence}-{uuid4().hex[:8]}",
            run_id=run_id,
            sequence=sequence,
            moderation_payload=moderation_payload,
            enqueued_at=datetime.now(timezone.utc).isoformat(),
        )

    def to_bytes(self) -> bytes:
        return json.dumps(
            {
                "task_id": self.task_id,
                "run_id": self.run_id,
                "sequence": self.sequence,
                "moderation_payload": self.moderation_payload,
                "enqueued_at": self.enqueued_at,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    @classmethod
    def from_bytes(cls, body: bytes) -> "RabbitMqModerationTask":
        data = json.loads(body.decode("utf-8"))
        return cls(
            task_id=str(data["task_id"]),
            run_id=str(data["run_id"]),
            sequence=int(data["sequence"]),
            moderation_payload=dict(data["moderation_payload"]),
            enqueued_at=str(data["enqueued_at"]),
        )


@dataclass(frozen=True)
class RabbitMqModerationResult:
    task_id: str
    run_id: str
    sequence: int
    ok: bool
    worker_id: str
    batch_size: int
    enqueued_at: str
    started_at: str
    completed_at: str
    moderation_response: dict[str, Any] | None = None
    action_result_response: dict[str, Any] | None = None
    error_kind: str | None = None
    error_message: str | None = None

    def to_bytes(self) -> bytes:
        return json.dumps(
            {
                "task_id": self.task_id,
                "run_id": self.run_id,
                "sequence": self.sequence,
                "ok": self.ok,
                "worker_id": self.worker_id,
                "batch_size": self.batch_size,
                "enqueued_at": self.enqueued_at,
                "started_at": self.started_at,
                "completed_at": self.completed_at,
                "moderation_response": self.moderation_response,
                "action_result_response": self.action_result_response,
                "error_kind": self.error_kind,
                "error_message": self.error_message,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    @classmethod
    def from_bytes(cls, body: bytes) -> "RabbitMqModerationResult":
        data = json.loads(body.decode("utf-8"))
        return cls(
            task_id=str(data["task_id"]),
            run_id=str(data["run_id"]),
            sequence=int(data["sequence"]),
            ok=bool(data["ok"]),
            worker_id=str(data["worker_id"]),
            batch_size=int(data["batch_size"]),
            enqueued_at=str(data["enqueued_at"]),
            started_at=str(data["started_at"]),
            completed_at=str(data["completed_at"]),
            moderation_response=data.get("moderation_response"),
            action_result_response=data.get("action_result_response"),
            error_kind=data.get("error_kind"),
            error_message=data.get("error_message"),
        )
