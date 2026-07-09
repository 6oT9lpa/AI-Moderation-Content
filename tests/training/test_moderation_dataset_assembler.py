from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_dataset_assembler import ModerationDatasetAssembler
from src.training.datasets.moderation_dataset_candidate import ModerationDatasetCandidate
from src.training.datasets.moderation_dataset_mix_config import ModerationDatasetMixConfig


def test_dataset_assembler_quality_filter_sanitizes_and_deduplicates() -> None:
    config = ModerationDatasetMixConfig.load("configs/training/dataset_mix_v1.yaml")
    assembler = ModerationDatasetAssembler(config)
    candidates = [
        _candidate("https://discord.gg/Qwerty user@example.com", ModerationLabel.INVITE, "manual_synthetic", "one"),
        _candidate("https://discord.gg/Qwerty user@example.com", ModerationLabel.INVITE, "manual_synthetic", "dupe"),
        _candidate("ok", ModerationLabel.SAFE, "project", "short"),
    ]

    filtered = assembler._quality_filter(candidates)

    assert len(filtered) == 1
    assert filtered[0].text == "<DISCORD_INVITE> <EMAIL>"


def test_dataset_assembler_reports_shortfalls_without_project_and_gated_spam() -> None:
    config = ModerationDatasetMixConfig.load("configs/training/dataset_mix_v1.yaml")
    candidates = [
        _candidate("spam text", ModerationLabel.SPAM, "manual_synthetic", "spam"),
        _candidate("safe text", ModerationLabel.SAFE, "manual_synthetic", "safe"),
    ]
    assembler = ModerationDatasetAssembler(config)

    selected, shortfalls = assembler._select_candidates(candidates, config.source_quotas())

    assert selected
    assert shortfalls["source:project"] == 9000
    assert shortfalls["source:russian_spam"] == 4000
    assert shortfalls["source:russian_toxic_comments"] == 6500
    assert shortfalls["source:russian_toxic_dvach"] == 2500
    assert shortfalls["source:russian_inappropriate"] == 6000
    assert shortfalls["source:russian_nsfw_benchmark"] == 2500
    assert shortfalls["source:russian_spam_fork"] == 2000
    assert shortfalls["source:russian_scam_spam_public"] == 2500
    assert shortfalls["source:russian_dialogues_safe"] == 5000
    assert shortfalls["source:russian_literature_safe"] == 2500
    assert shortfalls["label:SPAM"] == 5999
    assert shortfalls["label:SAFE"] == 19999


def _candidate(
    text: str,
    label: ModerationLabel,
    source: str,
    source_id: str,
) -> ModerationDatasetCandidate:
    return ModerationDatasetCandidate(
        text=text,
        labels=[label],
        primary_label=label,
        source_bucket=source,
        source_id=source_id,
        severity=0 if label == ModerationLabel.SAFE else 2,
    )
