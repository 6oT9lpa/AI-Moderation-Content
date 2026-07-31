from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Confidence = Annotated[float, Field(strict=True, ge=0.0, le=1.0)]
MediaModerationLabel = Literal["SCAM", "NSFW"]


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


MediaFailureAction = Literal["partial", "reject"]


class OcrProcessingPolicy(StrictFrozenModel):
    min_line_confidence: Confidence
    min_mean_confidence: Confidence
    min_text_length: int = Field(strict=True, ge=0, le=8_000)
    max_lines: int = Field(strict=True, ge=1, le=1_024)
    max_text_length: int = Field(strict=True, ge=1, le=32_000)
    preserve_line_breaks: bool
    discard_low_confidence_lines: bool
    process_empty_result: bool


class OcrNormalizationPolicy(StrictFrozenModel):
    unicode_nfkc: bool
    normalize_whitespace: bool
    remove_control_characters: bool
    remove_zero_width_characters: bool
    redact_personal_data: bool
    redact_payment_data: bool


class OcrModerationPolicy(StrictFrozenModel):
    run_tiny2: bool
    source: Literal["OCR"]
    merge_with_message_text: bool
    keep_attachment_provenance: bool


class OcrFailurePolicy(StrictFrozenModel):
    timeout: MediaFailureAction
    unavailable: MediaFailureAction
    invalid_result: MediaFailureAction


class OcrRuleSettings(StrictFrozenModel):
    enabled: bool
    required: bool
    allow_partial_results: bool
    processing: OcrProcessingPolicy
    normalization: OcrNormalizationPolicy
    moderation: OcrModerationPolicy
    failure_policy: OcrFailurePolicy

    @model_validator(mode="after")
    def validate_failure_semantics(self) -> "OcrRuleSettings":
        if self.required and self.allow_partial_results:
            raise ValueError("required OCR cannot allow partial results")
        return self


class OcrRulePolicy(StrictFrozenModel):
    version: str = Field(min_length=1, max_length=128)
    ocr: OcrRuleSettings


class YoloInferencePolicy(StrictFrozenModel):
    confidence_threshold: Confidence
    iou_threshold: Confidence
    max_detections: int = Field(strict=True, ge=1, le=1_000)


class YoloClassPolicy(StrictFrozenModel):
    enabled: bool
    moderation_label: MediaModerationLabel
    min_confidence: Confidence
    severity: int = Field(strict=True, ge=0, le=5)


class YoloAggregationPolicy(StrictFrozenModel):
    strategy: Literal["max_severity"]
    require_multiple_scam_signals: bool
    combine_with_ocr: bool
    combine_with_url_signals: bool
    preserve_detector_provenance: bool


class YoloFailurePolicy(StrictFrozenModel):
    timeout: MediaFailureAction
    unavailable: MediaFailureAction
    invalid_result: MediaFailureAction


class YoloRuleSettings(StrictFrozenModel):
    enabled: bool
    required: bool
    allow_partial_results: bool
    inference: YoloInferencePolicy
    classes: dict[str, YoloClassPolicy]
    aggregation: YoloAggregationPolicy
    failure_policy: YoloFailurePolicy

    @model_validator(mode="after")
    def validate_class_mapping(self) -> "YoloRuleSettings":
        if self.enabled and not self.classes:
            raise ValueError("enabled YOLO requires a detector class mapping")
        if self.required and self.allow_partial_results:
            raise ValueError("required YOLO cannot allow partial results")
        unknown = set(self.classes) - ALLOWED_YOLO_CLASSES
        if unknown:
            raise ValueError(f"unknown YOLO detector classes: {sorted(unknown)}")
        return self


class YoloRulePolicy(StrictFrozenModel):
    version: str = Field(min_length=1, max_length=128)
    yolo: YoloRuleSettings


class MediaRulePolicy(StrictFrozenModel):
    ocr: OcrRulePolicy
    yolo: YoloRulePolicy


ALLOWED_YOLO_CLASSES = frozenset(
    {
        "explicit_nudity",
        "exposed_genitals",
        "exposed_breast",
        "exposed_buttocks",
        "sexual_activity",
        "adult_toy",
        "casino_logo",
        "slot_machine_ui",
        "roulette",
        "betting_coupon",
        "gambling_banner",
        "suspicious_qr",
        "fake_giveaway_banner",
    }
)
