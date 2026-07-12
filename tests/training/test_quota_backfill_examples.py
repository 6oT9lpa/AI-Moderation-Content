from collections import Counter

from src.training.datasets.quota_backfill_examples import build_quota_backfill_candidates


def test_quota_backfill_is_unique_and_covers_failed_class_quotas() -> None:
    rows = build_quota_backfill_candidates()
    primary = Counter(row.primary_label.value for row in rows)

    unique_by_primary = Counter()
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.primary_label.value, row.text)
        if key not in seen:
            seen.add(key)
            unique_by_primary[row.primary_label.value] += 1

    assert unique_by_primary["SPAM"] >= 45_000
    assert unique_by_primary["SCAM"] >= 40_000
    assert unique_by_primary["SAFE"] >= 40_000
    assert unique_by_primary["THREAT"] >= 15_000
    assert unique_by_primary["EVASION"] >= 15_000
