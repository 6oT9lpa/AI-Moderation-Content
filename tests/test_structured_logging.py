from __future__ import annotations

from src.infrastructure.logging import get_logger
from tests.conftest import _build_expected_actual_comparison

logger = get_logger("tests")


def test_structured_log_comparison_marks_message_detection_mismatch() -> None:
    comparison = _build_expected_actual_comparison(
        {
            "expected": {
                "labels": ["SAFE"],
                "confidence": 1.0,
            },
            "detected_labels": ["SPAM"],
            "confidence": 0.72,
        },
    )

    logger.info("Structured comparison mismatch checked comparison=%s", comparison)

    assert comparison is not None
    assert comparison["status"] == "MISMATCH"
    assert comparison["expected"] == {"labels": ["SAFE"], "confidence": 1.0}
    assert comparison["actual"] == {"labels": ["SPAM"], "confidence": 0.72}
    assert comparison["differences"]


def test_structured_log_comparison_ignores_policy_settings_metadata() -> None:
    comparison = _build_expected_actual_comparison(
        {
            "preprocessing_expected": {
                "preprocessing_verdict": "SAFE",
                "detected_labels": [],
                "settings": {"flood": {"messages_10s": {"threshold": 10}}},
            },
            "preprocessing_actual": {
                "preprocessing_verdict": "SAFE",
                "detected_labels": [],
            },
        },
    )

    logger.info("Structured comparison settings ignore checked comparison=%s", comparison)

    assert comparison is not None
    assert comparison["status"] == "MATCH"
    assert "settings" not in comparison["expected"]["preprocessing"]


def test_structured_log_comparison_treats_labels_as_order_insensitive() -> None:
    comparison = _build_expected_actual_comparison(
        {
            "expected": {
                "labels": ["URL", "SPAM"],
            },
            "detected_labels": ["SPAM", "URL"],
        },
    )

    logger.info("Structured comparison label order checked comparison=%s", comparison)

    assert comparison is not None
    assert comparison["status"] == "MATCH"
    assert comparison["differences"] == []
