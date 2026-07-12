from collections import Counter

from src.training.datasets.russian_slang_examples import build_russian_slang_candidates


def test_russian_slang_pack_has_exact_requested_size_and_safe_contrasts() -> None:
    rows = build_russian_slang_candidates()
    counts = Counter(row.primary_label.value for row in rows)

    assert len(rows) == 50_000
    assert counts["SAFE"] == 25_000
    assert counts["TOXIC"] == 10_000
    assert counts["PROFANITY"] == 7_000
