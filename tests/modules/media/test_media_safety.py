from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image
from pydantic import ValidationError

from src.application.moderation_service import ModerationService
from src.contracts.image_attachment_input_schema import ImageAttachmentInputSchema
from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.domain.dto.dataset.dataset_collection_input import DatasetCollectionInput
from src.domain.media.ocr_result import OcrResult
from src.domain.media.ocr_status import OcrStatus
from src.infrastructure.media.pillow_image_rasterizer import PillowImageRasterizer
from src.infrastructure.repository.in_memory_dataset_collector_repository import InMemoryDatasetCollectorRepository
from src.modules.dataset.dataset_collector import DatasetCollector
from src.modules.media.image_metadata_extractor import ImageMetadataExtractor
from src.modules.media.known_scam_image_hash_config_loader import KnownScamImageHashConfigLoader
from src.modules.media.media_analyzer import MediaAnalyzer
from src.modules.media.media_rule_settings import MediaRuleSettings
from src.modules.decision.decision_engine import DecisionEngine
from src.modules.preprocessing.text_preprocessor import TextPreprocessor
from src.modules.rules.moderation_rule_engine import ModerationRuleEngine
from src.modules.rules.preprocessing_signal_adapter import PreprocessingSignalAdapter
from tests.modules.media.capturing_text_preprocessor import CapturingTextPreprocessor
from tests.modules.media.fake_ocr_service import FakeOcrService


def test_image_attachment_rejects_oversized_payload(structured_test_logger) -> None:
    oversized_bytes = b"a" * (8 * 1024 * 1024 + 1)
    with pytest.raises(ValidationError) as error:
        ImageAttachmentInputSchema(
            attachment_id="oversized",
            content_type="image/png",
            image_bytes=oversized_bytes,
        )
    actual = type(error.value).__name__
    structured_test_logger("input", {"image_byte_count": len(oversized_bytes)})
    structured_test_logger("detection", {"expected": "ValidationError", "actual": actual})

    assert actual == "ValidationError"


def test_rasterizer_rejects_image_over_pixel_limit(structured_test_logger) -> None:
    buffer = BytesIO()
    Image.new("1", (2_000, 2_000)).save(buffer, format="PNG")
    actual = PillowImageRasterizer(max_image_pixels=1_000_000).inspect(buffer.getvalue())
    structured_test_logger(
        "input",
        {"width": 2_000, "height": 2_000, "max_image_pixels": 1_000_000},
    )
    structured_test_logger("detection", {"expected": None, "actual": actual})

    assert actual is None


def test_metadata_uses_actual_image_byte_size(structured_test_logger) -> None:
    buffer = BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, format="PNG")
    attachment = ImageAttachmentInputSchema(
        attachment_id="metadata-size",
        content_type="image/png",
        file_size=1,
        image_bytes=buffer.getvalue(),
    )
    metadata = ImageMetadataExtractor().extract(attachment)
    expected = len(attachment.image_bytes)
    structured_test_logger(
        "input",
        {"declared_file_size": attachment.file_size, "actual_file_size": expected},
    )
    structured_test_logger("detection", {"expected": expected, "actual": metadata.file_size})

    assert metadata.file_size == expected


def test_known_hash_config_is_validated_and_is_cwd_independent(tmp_path, monkeypatch, structured_test_logger) -> None:
    invalid_path = tmp_path / "invalid_hashes.yaml"
    invalid_path.write_text(
        "version: known_scam_image_hashes_v1\nrecords:\n  - record_id: invalid\n    phash: not-a-hash\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as error:
        KnownScamImageHashConfigLoader.load(invalid_path)
    monkeypatch.chdir(tmp_path)
    default_records = KnownScamImageHashConfigLoader.load()
    actual = {"invalid_error": type(error.value).__name__, "default_record_count": len(default_records)}
    expected = {"invalid_error": "ValueError", "default_record_count": 0}
    structured_test_logger(
        "input",
        {"invalid_config_path": str(invalid_path), "working_directory": str(tmp_path)},
    )
    structured_test_logger("detection", {"expected": expected, "actual": actual})

    assert actual == expected


@pytest.mark.asyncio
async def test_media_analyzer_limits_attachment_count_and_ocr_text(structured_test_logger) -> None:
    analyzer = MediaAnalyzer(
        settings=MediaRuleSettings(max_image_attachments=2, max_ocr_text_length=256),
        ocr_service=FakeOcrService(OcrResult(text="x" * 512, status=OcrStatus.COMPLETED)),
    )
    attachments = tuple(
        ImageAttachmentInputSchema(attachment_id=f"image-{index}", content_type="image/png")
        for index in range(5)
    )
    result = await analyzer.analyze(attachments, message_text="")
    actual = {
        "attachment_count": result.image_count,
        "ocr_text_lengths": [len(attachment.ocr_result.text) for attachment in result.attachments],
    }
    expected = {"attachment_count": 2, "ocr_text_lengths": [256, 256]}
    structured_test_logger(
        "input",
        {"attachment_count": len(attachments), "fake_ocr_text_length": 512},
    )
    structured_test_logger("detection", {"expected": expected, "actual": actual})

    assert actual == expected


@pytest.mark.asyncio
async def test_default_media_analyzer_uses_tesseract_adapter_when_ocr_is_not_injected(structured_test_logger) -> None:
    attachment = ImageAttachmentInputSchema(attachment_id="default-ocr", content_type="image/png")
    result = await MediaAnalyzer().analyze((attachment,), message_text="")
    actual = {
        "ocr_status": result.attachments[0].ocr_result.status.value,
        "ocr_error": result.attachments[0].ocr_result.error,
    }
    expected = {"ocr_status": "SKIPPED", "ocr_error": "missing_image_bytes"}
    structured_test_logger("input", {"attachment_id": attachment.attachment_id})
    structured_test_logger("detection", {"expected": expected, "actual": actual})

    assert actual == expected


@pytest.mark.asyncio
async def test_moderation_service_preserves_attachment_context_and_typed_media_result(structured_test_logger) -> None:
    preprocessor = CapturingTextPreprocessor()
    service = ModerationService(
        preprocessor,  # type: ignore[arg-type]
        ModerationRuleEngine(),
        DecisionEngine(),
        PreprocessingSignalAdapter(),
        media_analyzer=MediaAnalyzer(
            ocr_service=FakeOcrService(
                OcrResult(text="casino email test@example.com", status=OcrStatus.COMPLETED)
            )
        ),
    )
    attachments = (
        ImageAttachmentInputSchema(attachment_id="service-1", content_type="image/png"),
        ImageAttachmentInputSchema(attachment_id="service-2", content_type="image/png"),
    )
    decision = await service.moderate("service-context", "bro @bot", attachments=attachments)
    assert preprocessor.last_payload is not None
    audit_ocr_text = decision.metadata["media_analysis"]["attachments"][0]["ocr_text"]
    actual = {
        "has_attachments": preprocessor.last_payload.has_attachments,
        "attachment_count": preprocessor.last_payload.attachment_count,
        "typed_media_result": decision.media_analysis is not None,
        "decision_audit_ocr_text": audit_ocr_text,
    }
    expected = {
        "has_attachments": True,
        "attachment_count": 2,
        "typed_media_result": True,
        "decision_audit_ocr_text": None,
    }
    structured_test_logger(
        "input",
        {"message_id": "service-context", "attachment_count": len(attachments)},
    )
    structured_test_logger("detection", {"expected": expected, "actual": actual})

    assert actual == expected


@pytest.mark.asyncio
async def test_dataset_collector_redacts_ocr_text_in_features_and_metadata(structured_test_logger) -> None:
    analyzer = MediaAnalyzer(
        ocr_service=FakeOcrService(
            OcrResult(
                text="casino test@example.com +79991234567 https://private.example/token token=abc123456",
                status=OcrStatus.COMPLETED,
            )
        )
    )
    attachment = ImageAttachmentInputSchema(attachment_id="dataset-sensitive", content_type="image/png")
    media_analysis = await analyzer.analyze((attachment,), message_text="bro")
    preprocessor = TextPreprocessor()
    context = await preprocessor.process(
        MessagePreprocessInputSchema(
            channel_id="channel",
            user_id="user",
            message_id="dataset-sensitive",
            raw_text="bro",
            has_attachments=True,
            attachment_count=1,
        )
    )
    rule_result = ModerationRuleEngine().evaluate(context.message_id, [])
    decision = DecisionEngine().decide(context.message_id, rule_result)
    repository = InMemoryDatasetCollectorRepository()
    await DatasetCollector(repository).collect(
        DatasetCollectionInput(
            context=context,
            rule_evaluation=rule_result,
            decision=decision,
            media_analysis=media_analysis,
        )
    )
    record = repository.records[0]
    expected = "casino <EMAIL> <PHONE> <URL_DOMAIN:private.example> <SECRET>"
    actual = {
        "features_ocr_text": record.features["attachments"][0]["ocr_text"],
        "metadata_ocr_text": record.metadata["media_analysis"]["attachments"][0]["ocr_text"],
    }
    structured_test_logger("input", {"raw_ocr_text": media_analysis.attachments[0].ocr_result.text})
    structured_test_logger(
        "detection",
        {"expected": {"features_ocr_text": expected, "metadata_ocr_text": expected}, "actual": actual},
    )

    assert actual == {"features_ocr_text": expected, "metadata_ocr_text": expected}
