from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.civil_comments_adapter import CivilCommentsAdapter


def _row(**updates: float) -> dict[str, float | str]:
    row: dict[str, float | str] = {
        "text": "example",
        "toxicity": 0.0,
        "severe_toxicity": 0.0,
        "obscene": 0.0,
        "threat": 0.0,
        "insult": 0.0,
        "identity_attack": 0.0,
        "sexual_explicit": 0.0,
    }
    row.update(updates)
    return row


def test_identity_attack_maps_to_hate_only_for_group_topic() -> None:
    labels, severity = CivilCommentsAdapter._labels_for_row(
        _row(identity_attack=0.9),
        ("gender",),
    )

    assert labels == {ModerationLabel.HATE, ModerationLabel.TOXIC}
    assert severity == 4


def test_family_threat_maps_to_threat_and_toxic() -> None:
    labels, severity = CivilCommentsAdapter._labels_for_row(
        _row(threat=0.8),
        ("family",),
    )

    assert labels == {ModerationLabel.THREAT, ModerationLabel.TOXIC}
    assert severity == 5


def test_low_score_target_example_is_safe_contrast() -> None:
    labels, severity = CivilCommentsAdapter._labels_for_row(_row(), ("race",))

    assert labels == {ModerationLabel.SAFE}
    assert severity == 0


def test_ambiguous_score_is_skipped() -> None:
    labels, severity = CivilCommentsAdapter._labels_for_row(
        _row(toxicity=0.4),
        ("family",),
    )

    assert labels is None
    assert severity == 0
