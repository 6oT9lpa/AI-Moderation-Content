from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_label_priority import resolve_primary_label


def test_resolve_primary_label_uses_dataset_priority_order() -> None:
    assert resolve_primary_label([ModerationLabel.SPAM, ModerationLabel.EVASION]) == ModerationLabel.SPAM
    assert resolve_primary_label([ModerationLabel.URL, ModerationLabel.EVASION]) == ModerationLabel.URL
    assert resolve_primary_label([ModerationLabel.SAFE, ModerationLabel.TOXIC]) == ModerationLabel.TOXIC
    assert resolve_primary_label([]) == ModerationLabel.SAFE
