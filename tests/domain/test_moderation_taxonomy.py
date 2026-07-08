from __future__ import annotations

import pytest

from src.domain.dataset.dataset_source import DatasetSource
from src.domain.dataset.feedback_type import FeedbackType
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.moderation.severity import Severity
from src.infrastructure.logging import get_logger

logger = get_logger("tests.preprocessing")


def test_moderation_taxonomy_contains_roadmap_values() -> None:
    logger.info(
        "Moderation taxonomy labels=%s actions=%s sources=%s feedback=%s",
        [label.value for label in ModerationLabel],
        [action.value for action in ModerationAction],
        [source.value for source in DatasetSource],
        [feedback.value for feedback in FeedbackType],
    )

    assert ModerationLabel.SAFE.value == "SAFE"
    assert ModerationLabel.URL.value == "URL"
    assert ModerationAction.DELETE_WARN.value == "DELETE_WARN"
    assert DatasetSource.MANUAL_SYNTHETIC.value == "manual_synthetic"
    assert FeedbackType.APPEAL_REJECTED.value == "appeal_rejected"


def test_severity_rejects_values_outside_roadmap_scale() -> None:
    logger.info("Severity validation started valid_value=%s invalid_value=%s", 5, 6)

    assert Severity(5).value == 5

    with pytest.raises(ValueError):
        Severity(6)
