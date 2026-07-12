from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_dataset_mix_config import ModerationDatasetMixConfig


def test_dataset_mix_config_matches_requested_quotas() -> None:
    config = ModerationDatasetMixConfig.load("configs/training/dataset_mix_v1.yaml")

    assert config.dataset.total_examples == 1050000
    assert config.dataset.negative_examples == 650000
    assert config.dataset.safe_examples == 400000
    assert sum(config.source_quotas().values()) == config.dataset.total_examples
    assert sum(config.negative_class_quotas().values()) == config.dataset.negative_examples
    assert config.negative_class_quotas()[ModerationLabel.NSFW] >= 40000
    assert config.negative_class_quotas()[ModerationLabel.TOXIC] >= 30000
    assert config.negative_class_quotas()[ModerationLabel.SCAM] >= 20000
    assert config.split_quotas() == {
        "train": 735000,
        "validation": 157500,
        "test": 157500,
    }
