from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_dataset_assembler import ModerationDatasetAssembler
from src.training.datasets.moderation_dataset_candidate import ModerationDatasetCandidate
from src.training.datasets.moderation_dataset_mix_config import ModerationDatasetMixConfig
from src.training.datasets.hard_eval_pack import build_hard_eval_pack


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
    assert "source:hard_eval_seed" not in shortfalls
    assert shortfalls["source:project"] == config.source_quotas()["project"]
    assert shortfalls["source:russian_spam"] == config.source_quotas()["russian_spam"]
    assert shortfalls["source:contextual_contrast"] == config.source_quotas()["contextual_contrast"]
    assert shortfalls["label:SPAM"] == config.negative_class_quotas()[ModerationLabel.SPAM] - 1
    assert shortfalls["label:SAFE"] == config.dataset.safe_examples - 1


def test_dataset_assembler_excludes_evaluation_pack_texts() -> None:
    config = ModerationDatasetMixConfig.load("configs/training/dataset_mix_v1.yaml")
    assembler = ModerationDatasetAssembler(config)
    row = build_hard_eval_pack()[2]

    filtered = assembler._quality_filter([
        _candidate(row["text"], ModerationLabel.SAFE, "manual_synthetic", "known-hard-case"),
    ])

    assert filtered == []


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
