import io
import json
from collections import Counter
from pathlib import Path

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.dataset_split_assigner import DatasetSplitAssigner
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema
from src.training.curation.russian_family_toxic_adapter import (
    RussianFamilyToxicAdapter,
)
from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher


TRAINING_CONFIG = Path("configs/training/rubert_tiny2.yaml")
def _adapter(matcher: SensitiveTopicMatcher) -> RussianFamilyToxicAdapter:
    return RussianFamilyToxicAdapter(
        schema=ModerationDatasetSchema.from_training_config(TRAINING_CONFIG),
        matcher=matcher,
        split_assigner=DatasetSplitAssigner(
            validation_fraction=0.01,
            seed="test-family-source",
        ),
    )


def test_adapter_keeps_independently_confirmed_family_threat(
    sensitive_topic_matcher: SensitiveTopicMatcher,
) -> None:
    handles = {"train": io.StringIO(), "validation": io.StringIO()}
    counts: Counter[str] = Counter()

    _adapter(sensitive_topic_matcher)._write_if_targeted(
        text="я убью твою мать",
        required_label=ModerationLabel.THREAT,
        record_id="source-1",
        handles=handles,
        counts=counts,
        source_key="threat",
    )

    payload = handles["train"].getvalue() or handles["validation"].getvalue()
    row = json.loads(payload)
    assert row["label_names"] == ["TOXIC", "THREAT"]
    assert "HATE" not in row["label_names"]
    assert sum(
        counts[f"threat_written_{split}"]
        for split in ("train", "validation")
    ) == 1


def test_adapter_sends_incidental_family_mention_to_review(
    sensitive_topic_matcher: SensitiveTopicMatcher,
) -> None:
    handles = {"train": io.StringIO(), "validation": io.StringIO()}
    counts: Counter[str] = Counter()

    _adapter(sensitive_topic_matcher)._write_if_targeted(
        text="мой брат дальнобойщик, а преступников надо убить",
        required_label=ModerationLabel.THREAT,
        record_id="source-2",
        handles=handles,
        counts=counts,
        source_key="threat",
    )

    assert handles["train"].getvalue() == ""
    assert handles["validation"].getvalue() == ""
    assert counts["threat_review_not_targeted"] == 1
