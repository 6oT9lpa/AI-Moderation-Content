import asyncio

from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, Sequence

import psycopg
from psycopg.rows import dict_row

from alembic import command
from alembic.config import Config as AlembicConfig

from src.infrastructure.database.cursor_result import DatabaseCursorResult
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


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

        logger.info("Database backend initialized target=%s", self.database_url)

    async def initialize(self) -> None:
        await self._run_migrations()
        await self._connect()
        await self._create_tables()

        logger.info("Database initialized successfully")

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

    async def _run_migrations(self) -> None:
        alembic_ini = self._find_project_file("alembic.ini")

        if alembic_ini is None:
            logger.warning("Alembic config not found, skipping migrations")
            return

        try:
            config = AlembicConfig(str(alembic_ini))
            config.set_main_option("sqlalchemy.url", self._get_alembic_database_url())

            await asyncio.to_thread(command.upgrade, config, "head")

            logger.info("Database migrations applied")

        except Exception as exc:
            logger.error(f"Failed to apply database migrations: {exc}", exc_info=True)
            raise

    async def _create_tables(self) -> None:
        for statement in self._get_create_table_statements():
            await self.execute(statement)

        for statement in self._get_create_index_statements():
            await self.execute(statement)

        logger.info("Database tables created successfully")

    async def execute(
        self,
        query: str,
        params: Sequence[Any] = (),
    ) -> DatabaseCursorResult:
        async def operation() -> DatabaseCursorResult:
            conn = await self.connect()

            async with self._lock:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)

                    rowcount = cursor.rowcount
                    lastrowid = await self._extract_returning_id(cursor)

                    logger.debug(
                        "Database query executed rowcount=%s lastrowid=%s",
                        rowcount,
                        lastrowid,
                    )

                    return DatabaseCursorResult(
                        rowcount=rowcount,
                        lastrowid=lastrowid,
                    )

        return await self._with_retry(operation)

    async def execute_many(
        self,
        query: str,
        values_list: Sequence[Sequence[Any]],
    ) -> DatabaseCursorResult:
        async def operation() -> DatabaseCursorResult:
            conn = await self.connect()

            async with self._lock:
                async with conn.cursor() as cursor:
                    await cursor.executemany(query, values_list)

                    logger.debug(
                        "Database batch query executed rowcount=%s batch_size=%s",
                        cursor.rowcount,
                        len(values_list),
                    )

                    return DatabaseCursorResult(rowcount=cursor.rowcount)

        return await self._with_retry(operation)

    async def fetch_one(
        self,
        query: str,
        params: Sequence[Any] = (),
    ) -> Optional[dict[str, Any]]:
        async def operation() -> Optional[dict[str, Any]]:
            conn = await self.connect()

            async with self._lock:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    row = await cursor.fetchone()

                    logger.debug("Database fetch_one executed found=%s", row is not None)

                    return dict(row) if row else None

        return await self._with_retry(operation)

    async def fetch_all(
        self,
        query: str,
        params: Sequence[Any] = (),
    ) -> list[dict[str, Any]]:
        async def operation() -> list[dict[str, Any]]:
            conn = await self.connect()

            async with self._lock:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    rows = await cursor.fetchall()

                    logger.debug("Database fetch_all executed rows_count=%s", len(rows))

                    return [dict(row) for row in rows]

        return await self._with_retry(operation)

    async def _extract_returning_id(
        self,
        cursor: psycopg.AsyncCursor,
    ) -> Optional[int]:
        if cursor.description is None:
            return None

        row = await cursor.fetchone()

        if not row:
            return None

        if "id" in row and row["id"] is not None:
            return int(row["id"])

        if "lastrowid" in row and row["lastrowid"] is not None:
            return int(row["lastrowid"])

        return None

    async def _with_retry[
        T
    ](
        self,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
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
            logger.error(
                "Database operation failed after retries attempts=%s error=%s",
                self.reconnect_attempts,
                last_exception,
                exc_info=True,
            )
            raise last_exception

        raise RuntimeError("Database operation failed without captured exception")

    def _find_project_file(self, filename: str) -> Optional[Path]:
        current_path = Path(__file__).resolve()

        for parent in current_path.parents:
            candidate = parent / filename

            if candidate.exists():
                return candidate

        return None

    def _get_alembic_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace(
                "postgresql://",
                "postgresql+psycopg://",
                1,
            )

        return self.database_url
    
    def _get_create_table_statements(self) -> list[str]:
        return [
            """
            CREATE TABLE IF NOT EXISTS ai_message_events (
                id BIGSERIAL PRIMARY KEY,

                message_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                user_id TEXT NOT NULL,

                event_type TEXT NOT NULL DEFAULT 'message_create',
                source TEXT NOT NULL DEFAULT 'real_safe',

                raw_text TEXT,
                normalized_text TEXT,
                text_hash TEXT,
                language TEXT,

                reply_to_message_id TEXT,

                has_attachments BOOLEAN NOT NULL DEFAULT FALSE,
                attachment_count INTEGER NOT NULL DEFAULT 0 CHECK (attachment_count >= 0),

                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMPTZ,
                retention_until TIMESTAMPTZ,

                UNIQUE (guild_id, message_id)
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS ai_message_features (
                id BIGSERIAL PRIMARY KEY,

                event_id BIGINT NOT NULL UNIQUE
                    REFERENCES ai_message_events(id)
                    ON DELETE CASCADE,

                text_length INTEGER NOT NULL DEFAULT 0 CHECK (text_length >= 0),
                word_count INTEGER NOT NULL DEFAULT 0 CHECK (word_count >= 0),
                line_count INTEGER NOT NULL DEFAULT 0 CHECK (line_count >= 0),

                url_count INTEGER NOT NULL DEFAULT 0 CHECK (url_count >= 0),
                mention_count INTEGER NOT NULL DEFAULT 0 CHECK (mention_count >= 0),
                role_mention_count INTEGER NOT NULL DEFAULT 0 CHECK (role_mention_count >= 0),
                channel_mention_count INTEGER NOT NULL DEFAULT 0 CHECK (channel_mention_count >= 0),
                emoji_count INTEGER NOT NULL DEFAULT 0 CHECK (emoji_count >= 0),

                uppercase_ratio NUMERIC(5, 4) NOT NULL DEFAULT 0 CHECK (uppercase_ratio >= 0 AND uppercase_ratio <= 1),
                repeated_char_score NUMERIC(5, 4) NOT NULL DEFAULT 0 CHECK (repeated_char_score >= 0 AND repeated_char_score <= 1),

                has_url BOOLEAN NOT NULL DEFAULT FALSE,
                has_invite BOOLEAN NOT NULL DEFAULT FALSE,
                has_attachment BOOLEAN NOT NULL DEFAULT FALSE,

                account_age_seconds BIGINT,
                member_age_seconds BIGINT,

                recent_message_count INTEGER NOT NULL DEFAULT 0 CHECK (recent_message_count >= 0),
                recent_duplicate_count INTEGER NOT NULL DEFAULT 0 CHECK (recent_duplicate_count >= 0),

                previous_warnings_count INTEGER NOT NULL DEFAULT 0 CHECK (previous_warnings_count >= 0),
                previous_timeouts_count INTEGER NOT NULL DEFAULT 0 CHECK (previous_timeouts_count >= 0),

                channel_is_whitelisted BOOLEAN NOT NULL DEFAULT FALSE,

                features JSONB NOT NULL DEFAULT '{}'::jsonb,

                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS ai_media_attachments (
                id BIGSERIAL PRIMARY KEY,

                event_id BIGINT NOT NULL
                    REFERENCES ai_message_events(id)
                    ON DELETE CASCADE,

                attachment_id TEXT NOT NULL,
                file_name TEXT,
                file_type TEXT,
                content_type TEXT,

                file_size BIGINT CHECK (file_size IS NULL OR file_size >= 0),

                width INTEGER CHECK (width IS NULL OR width >= 0),
                height INTEGER CHECK (height IS NULL OR height >= 0),
                aspect_ratio NUMERIC(10, 4),

                sha256 TEXT,
                phash TEXT,
                dhash TEXT,
                ahash TEXT,

                is_screenshot_like BOOLEAN NOT NULL DEFAULT FALSE,

                ocr_text TEXT,
                ocr_language TEXT,
                ocr_confidence NUMERIC(5, 4) CHECK (
                    ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)
                ),
                ocr_text_hash TEXT,

                ocr_has_money BOOLEAN NOT NULL DEFAULT FALSE,
                ocr_has_casino BOOLEAN NOT NULL DEFAULT FALSE,
                ocr_has_crypto BOOLEAN NOT NULL DEFAULT FALSE,
                ocr_has_bonus BOOLEAN NOT NULL DEFAULT FALSE,
                ocr_has_payment_words BOOLEAN NOT NULL DEFAULT FALSE,

                known_scam_hash_match BOOLEAN NOT NULL DEFAULT FALSE,

                storage_uri TEXT,

                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

                UNIQUE (event_id, attachment_id)
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS ai_analysis_results (
                id BIGSERIAL PRIMARY KEY,

                event_id BIGINT NOT NULL
                    REFERENCES ai_message_events(id)
                    ON DELETE CASCADE,

                stage TEXT NOT NULL,
                model TEXT,

                input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                output_json JSONB NOT NULL DEFAULT '{}'::jsonb,

                primary_label TEXT,
                labels TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],

                confidence NUMERIC(5, 4) CHECK (
                    confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
                ),
                probabilities JSONB NOT NULL DEFAULT '{}'::jsonb,

                rule_matches JSONB NOT NULL DEFAULT '[]'::jsonb,

                risk_score INTEGER CHECK (
                    risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)
                ),
                breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,

                latency_ms INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),

                error TEXT,

                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS ai_moderation_decisions (
                id BIGSERIAL PRIMARY KEY,

                event_id BIGINT NOT NULL
                    REFERENCES ai_message_events(id)
                    ON DELETE CASCADE,

                policy_version TEXT NOT NULL DEFAULT 'default',

                action TEXT NOT NULL,
                severity SMALLINT NOT NULL CHECK (severity >= 0 AND severity <= 5),

                reason_code TEXT,
                reason_text TEXT,

                action_taken BOOLEAN NOT NULL DEFAULT FALSE,
                action_success BOOLEAN,

                platform_error TEXT,
                punishment_id TEXT,

                review_status TEXT NOT NULL DEFAULT 'not_required',
                reviewed_by TEXT,
                reviewed_at TIMESTAMPTZ,

                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS ai_feedback_labels (
                id BIGSERIAL PRIMARY KEY,

                event_id BIGINT NOT NULL
                    REFERENCES ai_message_events(id)
                    ON DELETE CASCADE,

                decision_id BIGINT
                    REFERENCES ai_moderation_decisions(id)
                    ON DELETE SET NULL,

                labels TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
                primary_label TEXT,
                scam_subtype TEXT,

                severity SMALLINT CHECK (
                    severity IS NULL OR (severity >= 0 AND severity <= 5)
                ),

                recommended_action TEXT,

                moderator_id TEXT,

                feedback_type TEXT NOT NULL,
                false_positive BOOLEAN NOT NULL DEFAULT FALSE,
                false_negative BOOLEAN NOT NULL DEFAULT FALSE,
                needs_context BOOLEAN NOT NULL DEFAULT FALSE,

                annotator_confidence NUMERIC(5, 4) CHECK (
                    annotator_confidence IS NULL OR (annotator_confidence >= 0 AND annotator_confidence <= 1)
                ),

                annotation_source TEXT,
                notes TEXT,

                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS ai_rule_definitions (
                id BIGSERIAL PRIMARY KEY,

                rule_key TEXT NOT NULL UNIQUE,
                version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),

                category TEXT,
                label TEXT,
                severity SMALLINT CHECK (
                    severity IS NULL OR (severity >= 0 AND severity <= 5)
                ),

                enabled BOOLEAN NOT NULL DEFAULT TRUE,

                config JSONB NOT NULL DEFAULT '{}'::jsonb,
                description TEXT,

                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS ai_policy_versions (
                id BIGSERIAL PRIMARY KEY,

                policy_key TEXT NOT NULL,
                version TEXT NOT NULL,

                is_active BOOLEAN NOT NULL DEFAULT FALSE,

                config JSONB NOT NULL DEFAULT '{}'::jsonb,

                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                activated_at TIMESTAMPTZ,

                UNIQUE (policy_key, version)
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS ai_rule_match_events (
                id BIGSERIAL PRIMARY KEY,

                event_id BIGINT NOT NULL
                    REFERENCES ai_message_events(id)
                    ON DELETE CASCADE,

                rule_id BIGINT
                    REFERENCES ai_rule_definitions(id)
                    ON DELETE SET NULL,

                rule_key TEXT NOT NULL,
                rule_version INTEGER,

                matched BOOLEAN NOT NULL DEFAULT TRUE,

                label TEXT,
                severity SMALLINT CHECK (
                    severity IS NULL OR (severity >= 0 AND severity <= 5)
                ),

                score_delta INTEGER NOT NULL DEFAULT 0,

                evidence JSONB NOT NULL DEFAULT '{}'::jsonb,

                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ]
    
    def _get_create_index_statements(self) -> list[str]:
        return [
            """
            CREATE INDEX IF NOT EXISTS idx_ai_message_events_guild_created_at
            ON ai_message_events (guild_id, created_at DESC)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_message_events_user_created_at
            ON ai_message_events (user_id, created_at DESC)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_message_events_channel_created_at
            ON ai_message_events (channel_id, created_at DESC)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_message_events_source
            ON ai_message_events (source)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_message_events_text_hash
            ON ai_message_events (text_hash)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_message_events_retention_until
            ON ai_message_events (retention_until)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_media_attachments_event_id
            ON ai_media_attachments (event_id)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_media_attachments_sha256
            ON ai_media_attachments (sha256)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_media_attachments_ocr_text_hash
            ON ai_media_attachments (ocr_text_hash)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_analysis_results_event_stage
            ON ai_analysis_results (event_id, stage)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_analysis_results_primary_label
            ON ai_analysis_results (primary_label)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_analysis_results_risk_score
            ON ai_analysis_results (risk_score)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_moderation_decisions_event_id
            ON ai_moderation_decisions (event_id)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_moderation_decisions_action
            ON ai_moderation_decisions (action)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_moderation_decisions_created_at
            ON ai_moderation_decisions (created_at DESC)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_feedback_labels_event_id
            ON ai_feedback_labels (event_id)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_feedback_labels_primary_label
            ON ai_feedback_labels (primary_label)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_feedback_labels_feedback_type
            ON ai_feedback_labels (feedback_type)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_rule_match_events_event_id
            ON ai_rule_match_events (event_id)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_ai_rule_match_events_rule_key
            ON ai_rule_match_events (rule_key)
            """,
        ]