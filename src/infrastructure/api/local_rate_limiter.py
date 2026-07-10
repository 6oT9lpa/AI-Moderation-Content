import asyncio
from collections import OrderedDict
from time import monotonic


class LocalRateLimiter:
    def __init__(self, limit: int, window_seconds: int, max_keys: int = 5_000) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._max_keys = max_keys
        self._history: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = monotonic()
        async with self._lock:
            entries = [timestamp for timestamp in self._history.pop(key, []) if now - timestamp < self._window_seconds]
            allowed = len(entries) < self._limit
            if allowed:
                entries.append(now)
            self._history[key] = entries
            while len(self._history) > self._max_keys:
                self._history.popitem(last=False)
            return allowed
