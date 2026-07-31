from __future__ import annotations

from datetime import datetime

from psycopg.types.json import Jsonb

from src.application.ports.media.media_attachment_repository import MediaAttachmentRepository
from src.domain.media.media_attachment_record import MediaAttachmentRecord
from src.domain.media.media_hashes import MediaHashes
from src.infrastructure.database.connection import DatabaseConnection
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class PostgresqlMediaAttachmentRepository(MediaAttachmentRepository):
    def __init__(self, database: DatabaseConnection) -> None:
        self._database = database

    async def save(self, record: MediaAttachmentRecord) -> None:
        hashes = record.hashes
        await self._database.execute(
            """
            INSERT INTO ai_media_attachments (
                event_id, attachment_id, file_name, declared_mime, detected_mime,
                file_size, width, height, sha256, phash, dhash, ahash,
                is_screenshot_like, ocr_text, ocr_language, ocr_confidence,
                ocr_text_hash, ocr_flags_json, known_scam_hash_match, storage_uri,
                retention_until
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id, attachment_id) DO UPDATE SET
                file_name = EXCLUDED.file_name,
                declared_mime = EXCLUDED.declared_mime,
                detected_mime = EXCLUDED.detected_mime,
                file_size = EXCLUDED.file_size,
                width = EXCLUDED.width,
                height = EXCLUDED.height,
                sha256 = EXCLUDED.sha256,
                phash = EXCLUDED.phash,
                dhash = EXCLUDED.dhash,
                ahash = EXCLUDED.ahash,
                is_screenshot_like = EXCLUDED.is_screenshot_like,
                ocr_text = EXCLUDED.ocr_text,
                ocr_language = EXCLUDED.ocr_language,
                ocr_confidence = EXCLUDED.ocr_confidence,
                ocr_text_hash = EXCLUDED.ocr_text_hash,
                ocr_flags_json = EXCLUDED.ocr_flags_json,
                known_scam_hash_match = EXCLUDED.known_scam_hash_match,
                storage_uri = EXCLUDED.storage_uri,
                retention_until = EXCLUDED.retention_until,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                record.event_id,
                record.attachment_id,
                record.file_name,
                record.declared_mime,
                record.detected_mime,
                record.file_size,
                record.width,
                record.height,
                hashes.sha256 if hashes else None,
                hashes.phash if hashes else None,
                hashes.dhash if hashes else None,
                hashes.ahash if hashes else None,
                record.screenshot_like,
                record.redacted_ocr_text,
                record.ocr_language,
                record.ocr_confidence,
                record.ocr_text_hash,
                Jsonb(list(record.ocr_flags)),
                record.known_hash_match,
                record.storage_uri,
                record.retention_until,
            ),
        )
        logger.info(
            "Media attachment persisted event_id=%s attachment_id=%s hash_prefix=%s",
            record.event_id,
            record.attachment_id,
            hashes.sha256[:12] if hashes else None,
        )

    async def find_by_identity(self, event_id: int, attachment_id: str) -> MediaAttachmentRecord | None:
        row = await self._database.fetch_one(
            """
            SELECT attachment.*, event.guild_id
            FROM ai_media_attachments AS attachment
            JOIN ai_message_events AS event ON event.id = attachment.event_id
            WHERE attachment.event_id = %s AND attachment.attachment_id = %s
            """,
            (event_id, attachment_id),
        )
        return self._to_record(row)

    async def find_recent_by_hash(
        self,
        guild_id: str,
        sha256: str,
        not_before: datetime,
    ) -> MediaAttachmentRecord | None:
        row = await self._database.fetch_one(
            """
            SELECT attachment.*, event.guild_id
            FROM ai_media_attachments AS attachment
            JOIN ai_message_events AS event ON event.id = attachment.event_id
            WHERE event.guild_id = %s
              AND attachment.sha256 = %s
              AND attachment.created_at >= %s
              AND (attachment.retention_until IS NULL OR attachment.retention_until > CURRENT_TIMESTAMP)
            ORDER BY attachment.created_at DESC
            LIMIT 1
            """,
            (guild_id, sha256, not_before),
        )
        return self._to_record(row)

    @staticmethod
    def _to_record(row: dict | None) -> MediaAttachmentRecord | None:
        if row is None:
            return None
        hashes = None
        if row.get("sha256") and row.get("phash") and row.get("dhash") and row.get("ahash"):
            hashes = MediaHashes(
                sha256=row["sha256"],
                phash=row["phash"],
                dhash=row["dhash"],
                ahash=row["ahash"],
            )
        return MediaAttachmentRecord(
            event_id=int(row["event_id"]),
            guild_id=str(row["guild_id"]),
            attachment_id=str(row["attachment_id"]),
            file_name=row.get("file_name"),
            declared_mime=str(row.get("declared_mime") or row.get("content_type") or "application/octet-stream"),
            detected_mime=row.get("detected_mime"),
            file_size=int(row.get("file_size") or 0),
            width=row.get("width"),
            height=row.get("height"),
            hashes=hashes,
            screenshot_like=bool(row.get("is_screenshot_like", False)),
            redacted_ocr_text=row.get("ocr_text"),
            ocr_language=row.get("ocr_language"),
            ocr_confidence=float(row["ocr_confidence"]) if row.get("ocr_confidence") is not None else None,
            ocr_text_hash=row.get("ocr_text_hash"),
            ocr_flags=tuple(row.get("ocr_flags_json") or ()),
            known_hash_match=bool(row.get("known_scam_hash_match", False)),
            storage_uri=row.get("storage_uri"),
            retention_until=row.get("retention_until") or row["created_at"],
        )

