from __future__ import annotations

from collections import Counter

from src.training.datasets.synthetic_discord_examples import build_contextual_contrast_candidates
from src.training.datasets.training_text_sanitizer import TrainingTextSanitizer


def test_contextual_contrast_candidates_are_unique_and_cover_all_labels() -> None:
    candidates = build_contextual_contrast_candidates()

    assert len(candidates) == 200000
    assert len({candidate.text for candidate in candidates}) == len(candidates)
    sanitizer = TrainingTextSanitizer()
    assert len({sanitizer.sanitize(candidate.text) for candidate in candidates}) == len(candidates)
    assert all(" #" not in candidate.text for candidate in candidates)
    assert Counter(candidate.primary_label.value for candidate in candidates) == {
        "SAFE": 80000,
        "SPAM": 24000,
        "INVITE": 18000,
        "ADVERTISEMENT": 12000,
        "SCAM": 18000,
        "TOXIC": 12000,
        "HATE": 8400,
        "THREAT": 6000,
        "NSFW": 6000,
        "EVASION": 9600,
        "URL": 6000,
    }
