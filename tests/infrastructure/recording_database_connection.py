from __future__ import annotations

from typing import Any, Sequence


class RecordingDatabaseConnection:
    def __init__(self) -> None:
        self.queries: list[tuple[str, Sequence[Any]]] = []

    async def execute(self, query: str, params: Sequence[Any] = ()) -> None:
        self.queries.append((query, params))
