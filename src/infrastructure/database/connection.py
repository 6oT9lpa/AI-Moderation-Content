from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import psycopg
from alembic import command
from alembic.config import Config as AlembicConfig
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.engine import URL, make_url

from src.infrastructure.database.cursor_result import DatabaseCursorResult
from src.infrastructure.database.database_url import redact_database_url
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class DatabaseSession:
    """Queries bound to one already-owned PostgreSQL connection."""

    def __init__(self, connection: psycopg.AsyncConnection) -> None:
        self._connection = connection

    async def execute(
        self,
        query: str,
        params: Sequence[Any] = (),
    ) -> DatabaseCursorResult:
        async with self._connection.cursor() as cursor:
            await cursor.execute(query, params)
            return DatabaseCursorResult(
                rowcount=cursor.rowcount,
                lastrowid=await self._extract_returning_id(cursor),
            )

    async def execute_many(
        self,
        query: str,
        values_list: Sequence[Sequence[Any]],
    ) -> DatabaseCursorResult:
        async with self._connection.cursor() as cursor:
            await cursor.executemany(query, values_list)
            return DatabaseCursorResult(rowcount=cursor.rowcount)

    async def fetch_one(
        self,
        query: str,
        params: Sequence[Any] = (),
    ) -> Optional[dict[str, Any]]:
        async with self._connection.cursor() as cursor:
            await cursor.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(
        self,
        query: str,
        params: Sequence[Any] = (),
    ) -> list[dict[str, Any]]:
        async with self._connection.cursor() as cursor:
            await cursor.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    async def _extract_returning_id(cursor: psycopg.AsyncCursor) -> Optional[int]:
        if cursor.description is None:
            return None
        row = await cursor.fetchone()
        if not row:
            return None
        value = row.get("id", row.get("lastrowid"))
        return int(value) if value is not None else None


class DatabaseConnection:
    def __init__(
        self,
        database_url: str,
        *,
        reconnect_attempts: int = 3,
        reconnect_delay: float = 5.0,
    ) -> None:
        self.database_url = database_url
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self._connection: Optional[psycopg.AsyncConnection] = None
        self._lock = asyncio.Lock()
        logger.info(
            "Database backend initialized target=%s",
            redact_database_url(self.database_url),
        )

    async def initialize(self) -> None:
        await self._connect()
        await self._run_migrations()
        logger.info("Database initialized successfully")

    async def connect(self) -> psycopg.AsyncConnection:
        return await self._connect()

    async def close(self) -> None:
        await self._close()

    async def _connect(self) -> psycopg.AsyncConnection:
        async with self._lock:
            if self._connection is None or self._connection.closed:
                self._connection = await psycopg.AsyncConnection.connect(
                    self.database_url,
                    autocommit=True,
                    row_factory=dict_row,
                )
                logger.info("Database connection established")
            return self._connection

    async def _close(self) -> None:
        async with self._lock:
            if self._connection is not None and not self._connection.closed:
                await self._connection.close()
                logger.info("Database connection closed")
            self._connection = None

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[DatabaseSession]:
        """Own one atomic transaction; callers must keep network I/O outside it."""
        connection = await self.connect()
        try:
            async with self._lock:
                async with connection.transaction():
                    yield DatabaseSession(connection)
        except psycopg.OperationalError:
            await self.close()
            raise

    async def execute(
        self,
        query: str,
        params: Sequence[Any] = (),
    ) -> DatabaseCursorResult:
        async def operation() -> DatabaseCursorResult:
            connection = await self.connect()
            async with self._lock:
                return await DatabaseSession(connection).execute(query, params)

        return await self._with_retry(operation)

    async def execute_many(
        self,
        query: str,
        values_list: Sequence[Sequence[Any]],
    ) -> DatabaseCursorResult:
        async def operation() -> DatabaseCursorResult:
            connection = await self.connect()
            async with self._lock:
                return await DatabaseSession(connection).execute_many(
                    query, values_list
                )

        return await self._with_retry(operation)

    async def fetch_one(
        self,
        query: str,
        params: Sequence[Any] = (),
    ) -> Optional[dict[str, Any]]:
        async def operation() -> Optional[dict[str, Any]]:
            connection = await self.connect()
            async with self._lock:
                return await DatabaseSession(connection).fetch_one(query, params)

        return await self._with_retry(operation)

    async def fetch_all(
        self,
        query: str,
        params: Sequence[Any] = (),
    ) -> list[dict[str, Any]]:
        async def operation() -> list[dict[str, Any]]:
            connection = await self.connect()
            async with self._lock:
                return await DatabaseSession(connection).fetch_all(query, params)

        return await self._with_retry(operation)

    async def _with_retry(self, operation: Callable[[], Awaitable[Any]]) -> Any:
        delay = self.reconnect_delay
        last_exception: Optional[BaseException] = None
        for attempt in range(1, self.reconnect_attempts + 1):
            try:
                return await operation()
            except psycopg.OperationalError as exc:
                last_exception = exc
                await self.close()
                if attempt >= self.reconnect_attempts:
                    break
                logger.warning(
                    "Database operation failed, retrying delay=%.2fs attempt=%s/%s error=%s",
                    delay,
                    attempt,
                    self.reconnect_attempts,
                    exc,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)
        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Database operation failed without captured exception")

    async def _run_migrations(self) -> None:
        alembic_ini = self._find_project_file("alembic.ini")
        if alembic_ini is None:
            raise RuntimeError("Alembic config not found")
        config = AlembicConfig(str(alembic_ini))
        # ConfigParser treats percent-encoded URL characters as interpolation markers.
        config.set_main_option(
            "sqlalchemy.url", self._get_alembic_database_url().replace("%", "%%")
        )
        await asyncio.to_thread(command.upgrade, config, "head")
        logger.info("Database migrations applied")

    def _find_project_file(self, filename: str) -> Optional[Path]:
        current_path = Path(__file__).resolve()
        for parent in current_path.parents:
            candidate = parent / filename
            if candidate.exists():
                return candidate
        return None

    def _get_alembic_database_url(self) -> str:
        if "://" in self.database_url:
            parsed = make_url(self.database_url)
            return parsed.set(drivername="postgresql+psycopg").render_as_string(
                hide_password=False
            )
        parts = conninfo_to_dict(self.database_url)
        return URL.create(
            "postgresql+psycopg",
            username=parts.get("user"),
            password=parts.get("password"),
            host=parts.get("host"),
            port=int(parts["port"]) if parts.get("port") else None,
            database=parts.get("dbname"),
        ).render_as_string(hide_password=False)
