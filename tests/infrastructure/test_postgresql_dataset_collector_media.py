from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.domain.media.image_hashes import ImageHashes
from src.domain.media.image_metadata import ImageMetadata
from src.domain.media.media_analysis_result import MediaAnalysisResult
from src.domain.media.media_attachment_analysis import MediaAttachmentAnalysis
from src.domain.media.media_risk_result import MediaRiskResult
from src.domain.media.ocr_features import OcrFeatures
from src.domain.media.ocr_result import OcrResult
from src.domain.media.ocr_status import OcrStatus
from src.infrastructure.repository.postgresql_dataset_collector_repository import (
    PostgresqlDatasetCollectorRepository,
)
from src.modules.dataset.media_analysis_sanitizer import MediaAnalysisSanitizer
from tests.infrastructure.recording_database_connection import RecordingDatabaseConnection


@pytest.mark.asyncio
async def test_postgresql_media_attachment_persists_ocr_status_and_error(structured_test_logger) -> None:
    database = RecordingDatabaseConnection()
    repository = PostgresqlDatasetCollectorRepository(database)  # type: ignore[arg-type]
    media_analysis = MediaAnalysisResult(
        attachments=(
            MediaAttachmentAnalysis(
                attachment_id="image-1",
                metadata=ImageMetadata(
                    file_name="sample.png",
                    content_type="image/png",
                    file_size=42,
                    width=10,
                    height=10,
                    aspect_ratio=1.0,
                    is_screenshot_like=False,
                ),
                hashes=ImageHashes(sha256="sha", phash="phash", dhash="dhash", ahash="ahash"),
                ocr_result=OcrResult(
                    status=OcrStatus.SKIPPED,
                    error="no_ocr_service_configured",
                ),
                ocr_features=OcrFeatures(
                    text_density=0.0,
                    money_amounts=(),
                    domains=(),
                    casino_keywords=(),
                    money_keywords=(),
                    bonus_keywords=(),
                    payment_keywords=(),
                    fake_news_keywords=(),
                    crypto_keywords=(),
                ),
            ),
        ),
        rule_matches=(),
        risk=MediaRiskResult(score=10, breakdown=(("has_image", 10),), requires_review=False, high_risk=False),
        labels=(),
        scam_subtype=None,
    )

    await repository._upsert_media_attachments(
        42,
        SimpleNamespace(media_analysis=media_analysis),
        MediaAnalysisSanitizer().sanitize(media_analysis),
    )

    query, params = database.queries[0]
    actual = {
        "placeholder_count": query.count("%s"),
        "parameter_count": len(params),
        "has_ocr_status_column": "ocr_status" in query,
        "has_ocr_error_column": "ocr_error" in query,
        "ocr_status": next(value for value in params if value == OcrStatus.SKIPPED.value),
        "ocr_error": next(value for value in params if value == "no_ocr_service_configured"),
    }
    expected = {
        "placeholder_count": 33,
        "parameter_count": 33,
        "has_ocr_status_column": True,
        "has_ocr_error_column": True,
        "ocr_status": "SKIPPED",
        "ocr_error": "no_ocr_service_configured",
    }
    structured_test_logger(
        "input",
        {"event_id": 42, "attachment_id": "image-1", "ocr_status": "SKIPPED"},
    )
    structured_test_logger("detection", {"expected": expected, "actual": actual})

    assert actual == expected


@pytest.mark.asyncio
async def test_postgresql_media_attachment_redacts_ocr_text_before_persistence(structured_test_logger) -> None:
    database = RecordingDatabaseConnection()
    repository = PostgresqlDatasetCollectorRepository(database)  # type: ignore[arg-type]
    media_analysis = MediaAnalysisResult(
        attachments=(
            MediaAttachmentAnalysis(
                attachment_id="image-sensitive",
                metadata=ImageMetadata(
                    file_name="sample.png",
                    content_type="image/png",
                    file_size=42,
                    width=10,
                    height=10,
                    aspect_ratio=1.0,
                    is_screenshot_like=False,
                ),
                hashes=ImageHashes(),
                ocr_result=OcrResult(
                    text="email test@example.com phone +79991234567 link https://secret.example/path token=abc123456",
                    status=OcrStatus.COMPLETED,
                ),
                ocr_features=OcrFeatures(
                    text_density=0.0,
                    money_amounts=(),
                    domains=(),
                    casino_keywords=(),
                    money_keywords=(),
                    bonus_keywords=(),
                    payment_keywords=(),
                    fake_news_keywords=(),
                    crypto_keywords=(),
                ),
            ),
        ),
        rule_matches=(),
        risk=MediaRiskResult(score=10, breakdown=(('has_image', 10),), requires_review=False, high_risk=False),
        labels=(),
        scam_subtype=None,
    )
    media_audit = MediaAnalysisSanitizer().sanitize(media_analysis)

    await repository._upsert_media_attachments(
        43,
        SimpleNamespace(media_analysis=media_analysis),
        media_audit,
    )

    _query, params = database.queries[0]
    persisted_ocr_text = next(
        value for value in params if isinstance(value, str) and "<EMAIL>" in value
    )
    expected = "email <EMAIL> phone <PHONE> link <URL_DOMAIN:secret.example> <SECRET>"
    structured_test_logger(
        "input",
        {"raw_ocr_text": media_analysis.attachments[0].ocr_result.text},
    )
    structured_test_logger(
        "detection",
        {"expected": expected, "actual": persisted_ocr_text},
    )

    assert persisted_ocr_text == expected
