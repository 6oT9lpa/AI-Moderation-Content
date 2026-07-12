from collections import Counter

from src.training.datasets.russian_robustness_examples import build_russian_robustness_candidates


def test_russian_robustness_pack_covers_new_primary_labels() -> None:
    rows = build_russian_robustness_candidates()
    primary_counts = Counter(row.primary_label.value for row in rows)

    assert primary_counts["PROFANITY"] >= 48_000
    assert primary_counts["POLITICS_IRL"] >= 24_000
    assert primary_counts["SCAM"] >= 20_000
    assert primary_counts["SAFE"] >= 14_000
    assert primary_counts["TOXIC"] >= 24_000
