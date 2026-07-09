from __future__ import annotations

from collections import Counter

from src.training.datasets.hard_eval_pack import build_hard_eval_pack
from src.training.datasets.unseen_hard_eval_pack import build_unseen_hard_eval_pack


def test_hard_eval_pack_has_expected_size_and_distribution() -> None:
    rows = build_hard_eval_pack()

    assert len(rows) == 100
    assert Counter(row["primary_label"] for row in rows) == {
        "SAFE": 20,
        "SCAM": 10,
        "NSFW": 10,
        "TOXIC": 10,
        "HATE": 10,
        "THREAT": 10,
        "INVITE": 6,
        "SPAM": 6,
        "ADVERTISEMENT": 6,
        "URL": 6,
        "EVASION": 6,
    }
    assert all(row["text"].strip() for row in rows)
    assert all(row["primary_label"] in row["labels"] for row in rows)


def test_unseen_hard_eval_pack_has_expected_size_and_distribution() -> None:
    rows = build_unseen_hard_eval_pack()

    assert len(rows) == 100
    assert Counter(row["primary_label"] for row in rows) == {
        "SAFE": 20,
        "SCAM": 10,
        "NSFW": 10,
        "TOXIC": 10,
        "HATE": 10,
        "THREAT": 10,
        "INVITE": 6,
        "SPAM": 6,
        "ADVERTISEMENT": 6,
        "URL": 6,
        "EVASION": 6,
    }
    assert all(row["text"].strip() for row in rows)
    assert all(row["primary_label"] in row["labels"] for row in rows)
    assert not {row["text"] for row in rows} & {row["text"] for row in build_hard_eval_pack()}
