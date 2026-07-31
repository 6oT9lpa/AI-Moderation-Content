from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.infrastructure.media.yaml_media_policy_defaults_provider import YamlMediaPolicyDefaultsProvider


CONFIG_DIR = Path(__file__).parents[2] / "configs" / "policies"


def test_loads_strict_immutable_media_policy_defaults() -> None:
    policy = _provider().get_defaults()

    assert policy.ocr.version == "ocr-policy-v1"
    assert policy.yolo.version == "yolo-policy-v1"
    assert policy.yolo.yolo.classes["casino_logo"].moderation_label == "SCAM"
    with pytest.raises(ValidationError):
        policy.ocr.ocr.processing.min_text_length = 9


@pytest.mark.parametrize(
    ("fragment", "replacement"),
    [
        ("min_line_confidence: 0.45", "min_line_confidence: 1.1"),
        ("source: \"OCR\"", "source: \"IMAGE_SCAM\""),
    ],
)
def test_rejects_invalid_ocr_policy(tmp_path: Path, fragment: str, replacement: str) -> None:
    invalid_ocr = tmp_path / "ocr.yaml"
    invalid_ocr.write_text(
        (CONFIG_DIR / "ocr_rules.yaml").read_text(encoding="utf-8").replace(fragment, replacement),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        _provider(ocr_path=invalid_ocr)


def test_rejects_unknown_detector_class(tmp_path: Path) -> None:
    invalid_yolo = tmp_path / "yolo.yaml"
    invalid_yolo.write_text(
        (CONFIG_DIR / "yolo_rules.yaml").read_text(encoding="utf-8").replace(
            "    explicit_nudity:", "    unknown_detector:"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="unknown YOLO detector classes"):
        _provider(yolo_path=invalid_yolo)


def test_rejects_image_scam_mapping(tmp_path: Path) -> None:
    invalid_yolo = tmp_path / "yolo.yaml"
    invalid_yolo.write_text(
        (CONFIG_DIR / "yolo_rules.yaml").read_text(encoding="utf-8").replace(
            'moderation_label: "SCAM"', 'moderation_label: "IMAGE_SCAM"', 1
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        _provider(yolo_path=invalid_yolo)


def test_rejects_duplicate_yaml_keys(tmp_path: Path) -> None:
    duplicate_ocr = tmp_path / "ocr.yaml"
    duplicate_ocr.write_text(
        (CONFIG_DIR / "ocr_rules.yaml").read_text(encoding="utf-8") + "\nversion: duplicate\n",
        encoding="utf-8",
    )

    with pytest.raises(yaml.constructor.ConstructorError, match="duplicate key"):
        _provider(ocr_path=duplicate_ocr)


def _provider(
    *,
    ocr_path: Path = CONFIG_DIR / "ocr_rules.yaml",
    yolo_path: Path = CONFIG_DIR / "yolo_rules.yaml",
) -> YamlMediaPolicyDefaultsProvider:
    return YamlMediaPolicyDefaultsProvider(ocr_path=ocr_path, yolo_path=yolo_path)
