import asyncio

import pytest

from src.application.api_moderation_service import ApiModerationService
from src.contracts.rules.moderation_rule_policy import ModerationRulePolicy
from src.domain.media.image_detection import ImageDetection
from src.domain.media.image_detection_result import ImageDetectionResult
from src.domain.media.media_analysis_bundle import MediaAnalysisBundle
from src.domain.media.media_attachment import MediaAttachment
from src.domain.media.media_attachment_analysis import MediaAttachmentAnalysis
from src.domain.media.media_attachment_status import MediaAttachmentStatus
from src.domain.media.ocr_result import OcrResult
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.moderation_signal import ModerationSignal
from src.domain.rules.signal_source import SignalSource


class _RubertStub:
    def classify(self, _text: str) -> object:
        return object()

    def to_signals(self, _result: object, _policy: ModerationRulePolicy) -> list[ModerationSignal]:
        return [
            ModerationSignal(
                source=SignalSource.RUBERT,
                label=ModerationLabel.SCAM,
                confidence=0.9,
                severity=4,
                risk_weight=50,
                reason="stub",
            )
        ]


def _service() -> ApiModerationService:
    service = object.__new__(ApiModerationService)
    service._rubert_classifier = _RubertStub()
    service._inference_semaphore = asyncio.Semaphore(1)
    return service


@pytest.mark.asyncio
async def test_ocr_scam_uses_scam_label_with_ocr_provenance() -> None:
    result = OcrResult(
        attachment_id="attachment-1",
        text="casino fake win",
        redacted_text="casino fake win",
        language="en",
        confidence=0.8,
        model_name="paddleocr-ru-en",
        model_version="1",
        processing_time_ms=1,
    )
    signals = await _service()._classify_ocr_text(
        result,
        ModerationRulePolicy(policy_id="test", version="1"),
        "correlation",
        "message",
    )
    assert signals[0].source == SignalSource.OCR
    assert signals[0].label == ModerationLabel.SCAM
    assert signals[0].confidence == 0.8
    assert signals[0].evidence["attachment_id"] == "attachment-1"


@pytest.mark.asyncio
async def test_image_mapping_uses_scam_nsfw_and_ignores_unknown_classes() -> None:
    attachment = MediaAttachment(
        attachment_id="attachment-1",
        download_url="https://cdn.discordapp.com/a.png",
        content_type="image/png",
        file_size=10,
    )
    analysis = MediaAttachmentAnalysis(
        attachment=attachment,
        status=MediaAttachmentStatus.ANALYZED,
        image_result=ImageDetectionResult(
            attachment_id=attachment.attachment_id,
            detections=(
                ImageDetection(detector_class="casino", confidence=0.9),
                ImageDetection(detector_class="explicit", confidence=0.9),
                ImageDetection(detector_class="unknown", confidence=1.0),
            ),
            model_name="detector",
            model_version="1",
            processing_time_ms=1,
        ),
    )
    signals, _ = await _service()._build_media_signals(
        MediaAnalysisBundle(attachments=(analysis,)),
        ModerationRulePolicy(policy_id="test", version="1"),
        "correlation",
        "message",
    )
    assert {(signal.source, signal.label) for signal in signals} == {
        (SignalSource.IMAGE, ModerationLabel.SCAM),
        (SignalSource.IMAGE, ModerationLabel.NSFW),
    }

