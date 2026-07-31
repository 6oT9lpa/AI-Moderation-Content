from pathlib import Path

from src.domain.media.ocr_line import OcrLine
from src.domain.media.ocr_result import OcrResult
from src.infrastructure.media.ocr_policy_result_processor import OcrPolicyResultProcessor
from src.infrastructure.media.ocr_text_processor import OcrTextProcessor
from src.infrastructure.media.yaml_media_policy_defaults_provider import YamlMediaPolicyDefaultsProvider


def test_ocr_policy_filters_lines_before_existing_normalization() -> None:
    policy = YamlMediaPolicyDefaultsProvider(
        ocr_path=Path("configs/policies/ocr_rules.yaml"),
        yolo_path=Path("configs/policies/yolo_rules.yaml"),
    ).get_defaults().ocr.ocr
    result = OcrResult(
        attachment_id="attachment-1",
        lines=(
            OcrLine(text="шум", confidence=0.10),
            OcrLine(text="Бонус\u200b 5000", confidence=0.99),
        ),
        text="unfiltered",
        redacted_text="unfiltered",
        model_name="ocr",
        model_version="v1",
        processing_time_ms=1,
    )

    filtered = OcrPolicyResultProcessor(OcrTextProcessor(8_000)).apply(result, policy)

    assert filtered is not None
    assert [line.text for line in filtered.lines] == ["Бонус\u200b 5000"]
    assert filtered.text == "Бонус 5000"
    assert filtered.confidence == 0.99
    assert filtered.text_hash is not None


def test_ocr_policy_discards_low_mean_confidence_result() -> None:
    policy = YamlMediaPolicyDefaultsProvider(
        ocr_path=Path("configs/policies/ocr_rules.yaml"),
        yolo_path=Path("configs/policies/yolo_rules.yaml"),
    ).get_defaults().ocr.ocr.model_copy(
        update={
            "processing": YamlMediaPolicyDefaultsProvider(
                ocr_path=Path("configs/policies/ocr_rules.yaml"),
                yolo_path=Path("configs/policies/yolo_rules.yaml"),
            ).get_defaults().ocr.ocr.processing.model_copy(
                update={"discard_low_confidence_lines": False, "min_mean_confidence": 0.95}
            )
        }
    )
    result = OcrResult(
        attachment_id="attachment-1",
        lines=(OcrLine(text="сомнительный текст", confidence=0.60),),
        model_name="ocr",
        model_version="v1",
        processing_time_ms=1,
    )

    assert OcrPolicyResultProcessor(OcrTextProcessor(8_000)).apply(result, policy) is None
