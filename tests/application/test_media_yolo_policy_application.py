from pathlib import Path

from src.application.media_moderation_service import MediaModerationService
from src.domain.media.image_detection import ImageDetection
from src.domain.media.image_detection_result import ImageDetectionResult
from src.infrastructure.media.yaml_media_policy_defaults_provider import YamlMediaPolicyDefaultsProvider


def test_guild_yolo_policy_filters_thresholds_and_applies_nms() -> None:
    policy = YamlMediaPolicyDefaultsProvider(
        ocr_path=Path("configs/policies/ocr_rules.yaml"),
        yolo_path=Path("configs/policies/yolo_rules.yaml"),
    ).get_defaults().yolo.yolo
    result = ImageDetectionResult(
        attachment_id="attachment-1",
        model_name="test-yolo",
        model_version="v1",
        processing_time_ms=1,
        detections=(
            ImageDetection(detector_class="explicit_nudity", confidence=0.80, bounding_box=(0, 0, 100, 100)),
            ImageDetection(detector_class="explicit_nudity", confidence=0.70, bounding_box=(2, 2, 98, 98)),
            ImageDetection(detector_class="suspicious_qr", confidence=0.70, bounding_box=(0, 0, 10, 10)),
            ImageDetection(detector_class="unknown", confidence=0.99, bounding_box=(0, 0, 5, 5)),
        ),
    )

    filtered = MediaModerationService._apply_yolo_policy(result, policy)

    assert len(filtered.detections) == 1
    assert filtered.detections[0].detector_class == "explicit_nudity"
    assert filtered.detections[0].confidence == 0.80
