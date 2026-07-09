from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_dataset_mix_config import ModerationDatasetMixConfig


def test_dataset_mix_config_matches_requested_quotas() -> None:
    config = ModerationDatasetMixConfig.load("configs/training/dataset_mix_v1.yaml")

    assert config.dataset.total_examples == 50000
    assert config.dataset.negative_examples == 30000
    assert config.dataset.safe_examples == 20000
    assert config.source_quotas() == {
        "project": 9000,
        "russian_toxicity": 2500,
        "russian_toxic_comments": 6500,
        "russian_toxic_dvach": 2500,
        "russian_inappropriate": 6000,
        "russian_nsfw_benchmark": 2500,
        "russian_spam": 4000,
        "russian_spam_fork": 2000,
        "russian_scam_spam_public": 2500,
        "russian_dialogues_safe": 5000,
        "russian_literature_safe": 2500,
        "manual_synthetic": 2500,
        "ai_generated_edge": 2500,
    }
    assert config.negative_class_quotas() == {
        ModerationLabel.SPAM: 6000,
        ModerationLabel.INVITE: 4500,
        ModerationLabel.ADVERTISEMENT: 3000,
        ModerationLabel.SCAM: 4500,
        ModerationLabel.TOXIC: 3000,
        ModerationLabel.HATE: 2100,
        ModerationLabel.THREAT: 1500,
        ModerationLabel.NSFW: 1500,
        ModerationLabel.EVASION: 2400,
        ModerationLabel.URL: 1500,
    }
    assert config.split_quotas() == {
        "train": 35000,
        "validation": 7500,
        "test": 7500,
    }
