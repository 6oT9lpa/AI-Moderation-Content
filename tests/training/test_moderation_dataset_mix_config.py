from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_dataset_mix_config import ModerationDatasetMixConfig


def test_dataset_mix_config_matches_requested_quotas() -> None:
    config = ModerationDatasetMixConfig.load("configs/training/dataset_mix_v1.yaml")

    assert config.dataset.total_examples == 200000
    assert config.dataset.negative_examples == 120000
    assert config.dataset.safe_examples == 80000
    assert config.source_quotas() == {
        "project": 6000,
        "project_raw": 6000,
        "russian_discord_chat_logs": 3000,
        "russian_telegram_chat_logs": 6000,
        "russian_dialogues_2": 20000,
        "russian_toxicity": 3000,
        "russian_toxic_comments": 12000,
        "russian_toxic_dvach": 8000,
        "russian_paradetox": 3000,
        "russian_react_hate": 6000,
        "russian_inappropriate": 12000,
        "russian_nsfw_benchmark": 3000,
        "russian_nsfw_fiction": 5000,
        "russian_spam": 6000,
        "russian_spam_fork": 3000,
        "russian_scam_spam_public": 2000,
        "phishing_url": 8000,
        "discord_phishing_scam": 5000,
        "russian_dialogues_safe": 11000,
        "russian_dialogsum_safe": 9000,
        "russian_literature_safe": 9000,
        "russian_kinship_hard_safe": 16000,
        "manual_synthetic": 20000,
        "contextual_contrast": 11000,
        "ai_generated_edge": 7000,
    }
    assert config.negative_class_quotas() == {
        ModerationLabel.SPAM: 24000,
        ModerationLabel.INVITE: 18000,
        ModerationLabel.ADVERTISEMENT: 12000,
        ModerationLabel.SCAM: 18000,
        ModerationLabel.TOXIC: 12000,
        ModerationLabel.HATE: 8400,
        ModerationLabel.THREAT: 6000,
        ModerationLabel.NSFW: 6000,
        ModerationLabel.EVASION: 9600,
        ModerationLabel.URL: 6000,
    }
    assert config.split_quotas() == {
        "train": 140000,
        "validation": 30000,
        "test": 30000,
    }
