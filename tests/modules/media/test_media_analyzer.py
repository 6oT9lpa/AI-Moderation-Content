from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from src.contracts.image_attachment_input_schema import ImageAttachmentInputSchema
from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.application.moderation_service import ModerationService
from src.domain.media.image_hashes import ImageHashes
from src.domain.media.known_scam_image_hash import KnownScamImageHash
from src.domain.media.ocr_result import OcrResult
from src.domain.media.ocr_status import OcrStatus
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.moderation.scam_subtype import ScamSubtype
from src.domain.dto.dataset.dataset_collection_input import DatasetCollectionInput
from src.infrastructure.repository.in_memory_dataset_collector_repository import InMemoryDatasetCollectorRepository
from src.modules.dataset.dataset_collector import DatasetCollector
from src.modules.decision.decision_engine import DecisionEngine
from src.modules.media.known_scam_image_hash_registry import KnownScamImageHashRegistry
from src.modules.media.known_scam_image_hash_config_loader import KnownScamImageHashConfigLoader
from src.modules.media.media_analyzer import MediaAnalyzer
from src.modules.media.media_signal_adapter import MediaSignalAdapter
from src.modules.media.null_ocr_service import NullOcrService
from src.modules.preprocessing.text_preprocessor import TextPreprocessor
from src.modules.rules.moderation_rule_engine import ModerationRuleEngine
from src.modules.rules.preprocessing_signal_adapter import PreprocessingSignalAdapter
from tests.modules.media.fake_ocr_service import FakeOcrService


def test_known_scam_hash_registry_matches_near_phash(structured_test_logger) -> None:
    registry = KnownScamImageHashRegistry(
        records=(
            KnownScamImageHash(
                record_id="casino-banner-v1",
                phash="ffffffffffffffff",
                scam_subtype=ScamSubtype.CASINO_BONUS,
            ),
        ),
        max_distance=2,
    )
    actual = registry.find_match(ImageHashes(phash="fffffffffffffffe"))
    structured_test_logger(
        "input",
        {
            "candidate_phash": "fffffffffffffffe",
            "known_phash": "ffffffffffffffff",
            "max_distance": 2,
        },
    )
    structured_test_logger(
        "detection",
        {
            "expected": {
                "record_id": "casino-banner-v1",
                "hash_type": "phash",
                "distance": 1,
                "scam_subtype": "casino_bonus",
            },
            "actual": actual.to_dict() if actual else None,
        },
    )

    assert actual is not None
    assert actual.record_id == "casino-banner-v1"
    assert actual.hash_type == "phash"
    assert actual.distance == 1
    assert actual.scam_subtype == ScamSubtype.CASINO_BONUS


def test_known_scam_hash_config_loader_builds_registry_records(tmp_path, structured_test_logger) -> None:
    config_path = tmp_path / "known_scam_image_hashes.yaml"
    config_path.write_text(
        """
version: \"known_scam_image_hashes_v1\"
records:
  - record_id: \"configured-casino-banner\"
    phash: \"ffffffffffffffff\"
    scam_subtype: \"casino_bonus\"
""".strip(),
        encoding="utf-8",
    )
    records = KnownScamImageHashConfigLoader.load(config_path)
    actual = records[0]
    structured_test_logger(
        "input",
        {"config_path": str(config_path), "record_count": len(records)},
    )
    structured_test_logger(
        "detection",
        {
            "expected": {
                "record_id": "configured-casino-banner",
                "phash": "ffffffffffffffff",
                "scam_subtype": "casino_bonus",
            },
            "actual": {
                "record_id": actual.record_id,
                "phash": actual.phash,
                "scam_subtype": actual.scam_subtype.value if actual.scam_subtype else None,
            },
        },
    )

    assert actual.record_id == "configured-casino-banner"
    assert actual.phash == "ffffffffffffffff"
    assert actual.scam_subtype == ScamSubtype.CASINO_BONUS


@pytest.mark.asyncio
async def test_null_ocr_service_reports_skipped_status(structured_test_logger) -> None:
    attachment = ImageAttachmentInputSchema(
        attachment_id="no-ocr-image",
        content_type="image/png",
    )
    result = await NullOcrService().extract(attachment)
    structured_test_logger(
        "input",
        {"attachment_id": attachment.attachment_id, "content_type": attachment.content_type},
    )
    structured_test_logger(
        "detection",
        {
            "expected": {"status": "SKIPPED", "error": "no_ocr_service_configured"},
            "actual": {"status": result.status.value, "error": result.error},
        },
    )

    assert result.status == OcrStatus.SKIPPED
    assert result.error == "no_ocr_service_configured"


@pytest.mark.asyncio
async def test_media_analyzer_marks_high_risk_casino_image_from_ocr(structured_test_logger) -> None:
    analyzer = MediaAnalyzer(
        ocr_service=FakeOcrService(
            OcrResult(
                text="РИА Новости: казино дарит бонус 10,000 ₽. Пополнить баланс USDT successfully.",
                language="ru",
                confidence=0.94,
            )
        )
    )
    attachment = ImageAttachmentInputSchema(
        attachment_id="image-1",
        content_type="image/png",
        file_name="casino.png",
        file_size=25_000,
        width=1280,
        height=720,
    )

    result = await analyzer.analyze((attachment,), message_text="bro @bot", account_age_days=5)
    actual = result.to_dict()
    structured_test_logger(
        "input",
        {
            "attachment": attachment.model_dump(mode="json"),
            "ocr_text": result.attachments[0].ocr_result.text,
            "media_risk": result.risk.to_dict(),
        },
    )
    structured_test_logger(
        "detection",
        {
            "expected": {
                "media_risk_score": 100,
                "media_labels": ["ADVERTISEMENT", "IMAGE_SCAM", "SCAM"],
                "scam_subtype": "casino_bonus",
                "known_scam_hash_match": False,
            },
            "actual": {
                "media_risk_score": actual["media_risk_score"],
                "media_labels": actual["media_labels"],
                "scam_subtype": actual["scam_subtype"],
                "known_scam_hash_match": actual["known_scam_hash_match"],
            },
        },
    )

    assert result.risk.score == 100
    assert result.risk.high_risk is True
    assert result.scam_subtype == ScamSubtype.CASINO_BONUS
    assert set(result.labels) == {
        ModerationLabel.SCAM,
        ModerationLabel.ADVERTISEMENT,
        ModerationLabel.IMAGE_SCAM,
    }
    assert result.rule_matches[0].rule_id == "media.ocr.high_risk_scam"


@pytest.mark.asyncio
async def test_media_analyzer_detects_repeated_scam_image_by_phash(structured_test_logger) -> None:
    image_buffer = BytesIO()
    Image.new("RGB", (1280, 720), color=(220, 40, 40)).save(image_buffer, format="PNG")
    attachment = ImageAttachmentInputSchema(
        attachment_id="known-image",
        content_type="image/png",
        image_bytes=image_buffer.getvalue(),
    )
    first_result = await MediaAnalyzer().analyze((attachment,), message_text="bro")
    phash = first_result.attachments[0].hashes.phash
    assert phash is not None
    analyzer = MediaAnalyzer(
        known_hash_registry=KnownScamImageHashRegistry(
            records=(
                KnownScamImageHash(
                    record_id="known-casino-image",
                    phash=phash,
                    scam_subtype=ScamSubtype.CASINO_BONUS,
                ),
            )
        )
    )

    result = await analyzer.analyze((attachment,), message_text="bro")
    structured_test_logger(
        "input",
        {
            "attachment_id": attachment.attachment_id,
            "image_size": len(attachment.image_bytes),
            "registered_phash": phash,
        },
    )
    structured_test_logger(
        "detection",
        {
            "expected": {
                "known_scam_hash_match": True,
                "media_risk_score": 90,
                "primary_rule_id": "media.image.known_scam_hash",
                "scam_subtype": "casino_bonus",
            },
            "actual": {
                "known_scam_hash_match": result.known_scam_hash_match,
                "media_risk_score": result.risk.score,
                "primary_rule_id": result.rule_matches[0].rule_id,
                "scam_subtype": result.scam_subtype.value if result.scam_subtype else None,
            },
        },
    )

    assert result.known_scam_hash_match is True
    assert result.risk.score == 90
    assert result.rule_matches[0].rule_id == "media.image.known_scam_hash"
    assert result.scam_subtype == ScamSubtype.CASINO_BONUS


@pytest.mark.asyncio
async def test_dataset_collector_preserves_media_audit_features(structured_test_logger) -> None:
    analyzer = MediaAnalyzer(
        ocr_service=FakeOcrService(
            OcrResult(text="casino бонус 10000 ₽ withdrawal", language="ru", confidence=0.91)
        )
    )
    attachment = ImageAttachmentInputSchema(
        attachment_id="image-dataset",
        content_type="image/jpeg",
        width=1280,
        height=720,
    )
    media_result = await analyzer.analyze((attachment,), message_text="@bot", account_age_days=2)
    context = await TextPreprocessor().process(
        MessagePreprocessInputSchema(
            channel_id="channel-1",
            user_id="user-1",
            message_id="media-message-1",
            raw_text="@bot",
            has_attachments=True,
            attachment_count=1,
        )
    )
    signals = []
    for match in media_result.rule_matches:
        signals.extend(MediaSignalAdapter().adapt(match))
    rule_result = ModerationRuleEngine().evaluate(context.message_id, signals)
    decision = DecisionEngine().decide(context.message_id, rule_result)
    repository = InMemoryDatasetCollectorRepository()
    collected = await DatasetCollector(repository).collect(
        DatasetCollectionInput(
            context=context,
            rule_evaluation=rule_result,
            decision=decision,
            media_analysis=media_result,
        )
    )
    record = repository.records[0]
    structured_test_logger(
        "input",
        {
            "message_id": context.message_id,
            "attachment_id": attachment.attachment_id,
            "ocr_text": media_result.attachments[0].ocr_result.text,
            "media_risk_score": media_result.risk.score,
        },
    )
    structured_test_logger(
        "detection",
        {
            "expected": {
                "image_count": 1,
                "media_risk_score": media_result.risk.score,
                "scam_subtype": "casino_bonus",
                "has_attachments": True,
            },
            "actual": {
                "image_count": record.features["image_count"],
                "media_risk_score": record.features["media_risk_score"],
                "scam_subtype": record.features["scam_subtype"],
                "has_attachments": record.has_attachments,
            },
        },
    )

    assert collected.event_id == 1
    assert record.media_analysis == media_result
    assert record.features["image_count"] == 1
    assert record.features["media_risk_score"] == media_result.risk.score
    assert record.features["scam_subtype"] == ScamSubtype.CASINO_BONUS.value


@pytest.mark.asyncio
async def test_moderation_service_adds_media_analysis_to_decision_audit(structured_test_logger) -> None:
    media_analyzer = MediaAnalyzer(
        ocr_service=FakeOcrService(
            OcrResult(text="casino бонус 10000 ₽ deposit usdt", language="ru", confidence=0.9)
        )
    )
    service = ModerationService(
        TextPreprocessor(),
        ModerationRuleEngine(),
        DecisionEngine(),
        PreprocessingSignalAdapter(),
        media_analyzer=media_analyzer,
    )
    attachment = ImageAttachmentInputSchema(
        attachment_id="service-image",
        content_type="image/png",
        width=1280,
        height=720,
    )

    decision = await service.moderate("service-media-message", "bro @bot", attachments=(attachment,))
    media_audit = decision.metadata["media_analysis"]
    structured_test_logger(
        "input",
        {
            "message_id": "service-media-message",
            "text": "bro @bot",
            "attachment_id": attachment.attachment_id,
        },
    )
    structured_test_logger(
        "detection",
        {
            "expected": {
                "primary_label": "SCAM",
                "media_risk_score": 100,
                "media_labels": ["ADVERTISEMENT", "IMAGE_SCAM", "SCAM"],
            },
            "actual": {
                "primary_label": decision.primary_label.value,
                "media_risk_score": media_audit["media_risk_score"],
                "media_labels": media_audit["media_labels"],
            },
        },
    )

    assert decision.primary_label == ModerationLabel.SCAM
    assert media_audit["media_risk_score"] == 100
