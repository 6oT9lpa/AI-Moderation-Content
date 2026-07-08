from __future__ import annotations

from typing import Any, Protocol


class QueueService(Protocol):
    async def publish(self, task: Any) -> None:
        ...

    async def consume(self) -> Any:
        ...
