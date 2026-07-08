from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.domain.moderation.moderation_label import ModerationLabel
from src.infrastructure.logging import get_logger
from src.modules.preprocessing.text_preprocessor import TextPreprocessor
from tests.fixtures.preprocessing_fixture_expectation_builder import PreprocessingFixtureExpectationBuilder

logger = get_logger("tests.preprocessing")

FIXTURE_DIR = Path("tests/fixtures/moderation/final_classes")
CASES_PER_LABEL = 50
PREPROCESSING_EXPECTATION_BUILDER = PreprocessingFixtureExpectationBuilder()


def _load_fixture_documents() -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []

    for path in sorted(FIXTURE_DIR.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        document["_path"] = str(path)
        documents.append(document)

    return documents


def _load_fixture_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    for document in _load_fixture_documents():
        for case in document["cases"]:
            case["_path"] = document["_path"]
            case["expected_preprocessing"] = PREPROCESSING_EXPECTATION_BUILDER.build(case)
            cases.append(case)

    return cases


def _build_actual_preprocessing_detection(context) -> dict[str, Any]:
    rule_matches = context.metadata.get("preprocessing_rule_matches", [])
    detected_labels = context.metadata.get("preprocessing_labels", [])
    confidences = [
        match.get("confidence")
        for match in rule_matches
        if isinstance(match, dict) and match.get("confidence") is not None
    ]

    return {
        "config_source": "configs/rules/preprocessing_rules.yaml",
        "preprocessing_verdict": "SAFE" if not detected_labels else "SIGNAL",
        "detected_labels": detected_labels,
        "rule_matches": rule_matches,
        "confidence": max(confidences) if confidences else None,
        "model_confidence": None,
    }


def test_final_class_fixture_files_match_moderation_labels() -> None:
    documents = _load_fixture_documents()
    fixture_labels = {document["label"] for document in documents}
    expected_labels = {label.value for label in ModerationLabel}

    logger.info(
        "Final class fixture labels checked expected=%s actual=%s",
        sorted(expected_labels),
        sorted(fixture_labels),
    )

    assert fixture_labels == expected_labels


@pytest.mark.parametrize("document", _load_fixture_documents(), ids=lambda document: document["label"])
def test_final_class_fixture_has_50_cases_per_label(document: dict[str, Any]) -> None:
    cases = document["cases"]
    case_ids = [case["id"] for case in cases]

    logger.info(
        "Final class fixture count checked file=%s label=%s count=%s",
        document["_path"],
        document["label"],
        len(cases),
    )

    assert document["case_count"] == CASES_PER_LABEL
    assert len(cases) == CASES_PER_LABEL
    assert len(set(case_ids)) == CASES_PER_LABEL


@pytest.mark.parametrize("case", _load_fixture_cases(), ids=lambda case: case["id"])
def test_final_class_fixture_case_schema(case: dict[str, Any], structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(**case["input"])
    expected_preprocessing = case["expected_preprocessing"]
    structured_test_logger(
        "output",
        {
            "schema": "MessagePreprocessInputSchema",
            "message_id": payload.message_id,
            "platform": payload.platform,
            "channel_id": payload.channel_id,
            "raw_text": payload.raw_text,
            "metadata": payload.metadata,
        },
    )
    structured_test_logger("expected", {"dataset": case["expected"], "preprocessing": expected_preprocessing})

    logger.info(
        "Final class fixture schema checked id=%s primary_label=%s message_id=%s",
        case["id"],
        case["primary_label"],
        payload.message_id,
    )

    assert case["primary_label"] in {label.value for label in ModerationLabel}
    assert case["primary_label"] == case["expected"]["primary_label"]
    assert case["primary_label"] in case["expected"]["labels"]
    assert "preprocessing_rule_settings" not in payload.metadata
    assert payload.message_id
    assert payload.channel_id
    assert payload.user_id


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _load_fixture_cases(), ids=lambda case: case["id"])
async def test_final_class_fixture_can_run_through_preprocessing(
    case: dict[str, Any],
    structured_test_logger,
) -> None:
    payload = MessagePreprocessInputSchema(**case["input"])
    context = await TextPreprocessor().process(payload)
    expected_preprocessing = case["expected_preprocessing"]
    actual_preprocessing = _build_actual_preprocessing_detection(context)

    structured_test_logger(
        "output",
        {
            "message_id": context.message_id,
            "normalized_text": context.normalized_text,
            "language": context.language,
            "urls": context.urls,
            "domains": context.domains,
            "invites": context.invites,
            "features": context.features.to_dict() if context.features else None,
        },
    )
    structured_test_logger(
        "detection",
        {
            "dataset_expected": case["expected"],
            "preprocessing_expected": expected_preprocessing,
            "preprocessing_actual": actual_preprocessing,
        },
    )

    logger.info(
        "Final class fixture preprocessed id=%s primary_label=%s message_id=%s normalized=%r features=%s",
        case["id"],
        case["primary_label"],
        context.message_id,
        context.normalized_text,
        context.features.to_dict() if context.features else None,
    )

    assert context.message_id == payload.message_id
    assert context.features is not None
    assert context.metadata["feature_version"] == "text_preprocessor_v1"
    assert actual_preprocessing["preprocessing_verdict"] == expected_preprocessing["preprocessing_verdict"]
    assert actual_preprocessing["detected_labels"] == expected_preprocessing["detected_labels"]
    assert actual_preprocessing["rule_matches"] == expected_preprocessing["rule_matches"]
    assert actual_preprocessing["confidence"] == expected_preprocessing["confidence"]
