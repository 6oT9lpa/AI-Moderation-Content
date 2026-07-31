from datetime import datetime, timezone

import pytest

from src.domain.media.media_analysis_record import MediaAnalysisRecord
from src.domain.media.media_analysis_stage import MediaAnalysisStage
from src.domain.media.media_attachment_record import MediaAttachmentRecord
from src.infrastructure.repository.postgresql_media_analysis_result_repository import (
    PostgresqlMediaAnalysisResultRepository,
)
from src.infrastructure.repository.postgresql_media_attachment_repository import (
    PostgresqlMediaAttachmentRepository,
)


class RecordingDatabase:
    def __init__(self, row: dict | None = None) -> None:
        self.row = row
        self.calls: list[tuple[str, tuple | list]] = []

    async def execute(self, query: str, parameters: tuple | list = ()) -> None:
        self.calls.append((query, parameters))

    async def fetch_one(self, query: str, parameters: tuple | list = ()) -> dict | None:
        self.calls.append((query, parameters))
        return self.row


@pytest.mark.asyncio
async def test_analysis_cache_lookup_requires_every_compatibility_version() -> None:
    database = RecordingDatabase(row=None)
    repository = PostgresqlMediaAnalysisResultRepository(database)  # type: ignore[arg-type]

    result = await repository.find_compatible(
        7,
        "attachment-1",
        MediaAnalysisStage.OCR,
        "paddleocr",
        "3.2:model-a",
        "media-v1",
        "policy-v4",
    )

    assert result is None
    query, parameters = database.calls[0]
    assert "model_name = %s" in query
    assert "model_version = %s" in query
    assert "input_version = %s" in query
    assert "policy_version = %s" in query
    assert parameters == (7, "attachment-1", "ocr", "paddleocr", "3.2:model-a", "media-v1", "policy-v4")


@pytest.mark.asyncio
async def test_analysis_save_uses_versioned_idempotency_key() -> None:
    database = RecordingDatabase()
    repository = PostgresqlMediaAnalysisResultRepository(database)  # type: ignore[arg-type]
    record = MediaAnalysisRecord(
        event_id=7,
        attachment_id="attachment-1",
        stage=MediaAnalysisStage.IMAGE,
        model_name="detector",
        model_version="v2",
        input_version="media-v1",
        policy_version="policy-v4",
        labels=("SCAM",),
    )

    await repository.save(record)

    query, parameters = database.calls[0]
    assert "ON CONFLICT" in query
    assert parameters[:7] == (7, "attachment-1", "image", "detector", "v2", "media-v1", "policy-v4")


@pytest.mark.asyncio
async def test_attachment_save_uses_message_attachment_identity() -> None:
    database = RecordingDatabase()
    repository = PostgresqlMediaAttachmentRepository(database)  # type: ignore[arg-type]
    record = MediaAttachmentRecord(
        event_id=7,
        guild_id="guild-1",
        attachment_id="attachment-1",
        declared_mime="image/png",
        file_size=42,
        retention_until=datetime.now(timezone.utc),
    )

    await repository.save(record)

    query, parameters = database.calls[0]
    assert "ON CONFLICT (event_id, attachment_id)" in query
    assert parameters[:5] == (7, "attachment-1", None, "image/png", None)
