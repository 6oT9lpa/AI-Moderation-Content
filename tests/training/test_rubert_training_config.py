from __future__ import annotations

from datetime import datetime

from src.domain.dataset.dataset_source import DatasetSource
from src.domain.dataset.feedback_type import FeedbackType
from src.domain.dto.dataset.training_example import TrainingExample
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel
from src.training.rubert.rubert_dataset_builder import RuBertDatasetBuilder
from src.training.rubert.rubert_label_schema import RuBertLabelSchema
from src.training.rubert.rubert_training_config import RuBertTrainingConfig


def test_rubert_training_config_loads_label_metadata() -> None:
    config = RuBertTrainingConfig.load("configs/training/rubert_tiny2.yaml")

    assert config.model.base_model_name == "cointegrated/rubert-tiny2"
    assert config.model.max_length > 0
    assert config.label_schema.label2id["SAFE"] == 0
    assert config.label_schema.label2id["PROFANITY"] == 6
    assert config.label_schema.label2id["POLITICS_IRL"] == 7
    assert config.label_schema.label2id["IMAGE_SCAM"] == 14
    assert config.to_transformers_metadata()["problem_type"] == "multi_label_classification"


def test_rubert_label_schema_encodes_multilabel_targets() -> None:
    schema = RuBertLabelSchema(labels=[ModerationLabel.SAFE, ModerationLabel.SPAM, ModerationLabel.SCAM])

    assert schema.encode_labels([ModerationLabel.SPAM, ModerationLabel.SCAM]) == [0.0, 1.0, 1.0]


def test_rubert_dataset_builder_uses_model_text_and_multihot_labels() -> None:
    config = RuBertTrainingConfig.load("configs/training/rubert_tiny2.yaml")
    example = TrainingExample(
        event_id=1,
        message_id="message-1",
        model_text="join <DISCORD_INVITE>",
        labels=[ModerationLabel.INVITE, ModerationLabel.SPAM],
        primary_label=ModerationLabel.INVITE,
        severity=3,
        source=DatasetSource.REAL_MODERATED,
        risk_score=43.0,
        decision_action=ModerationAction.REVIEW,
        feedback_type=FeedbackType.CONFIRMED,
        policy_version="1.0",
        created_at=datetime(2026, 7, 8),
    )

    [row] = RuBertDatasetBuilder(config.label_schema).build_rows([example])

    assert row["text"] == "join <DISCORD_INVITE>"
    assert row["label_names"] == ["INVITE", "SPAM"]
    assert row["labels"][config.label_schema.label2id["INVITE"]] == 1.0
    assert row["labels"][config.label_schema.label2id["SPAM"]] == 1.0
    assert sum(row["labels"]) == 2.0


def test_rubert_dataset_builder_resolves_primary_label_by_dataset_priority() -> None:
    config = RuBertTrainingConfig.load("configs/training/rubert_tiny2.yaml")
    example = TrainingExample(
        event_id=1,
        message_id="message-priority",
        model_text="mixed labels",
        labels=[ModerationLabel.SPAM, ModerationLabel.EVASION],
        primary_label=ModerationLabel.EVASION,
        severity=2,
        source=DatasetSource.REAL_MODERATED,
        risk_score=50.0,
        decision_action=ModerationAction.REVIEW,
        feedback_type=FeedbackType.CONFIRMED,
        policy_version="1.0",
        created_at=datetime(2026, 7, 8),
    )

    [row] = RuBertDatasetBuilder(config.label_schema).build_rows([example])

    assert row["primary_label"] == "SPAM"
