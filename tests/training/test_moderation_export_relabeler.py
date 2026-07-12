from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_export_relabeler import ModerationExportRelabeler
from src.training.rubert.rubert_label_schema import RuBertLabelSchema


def test_relabel_row_marks_safe_url_as_url() -> None:
    row = {
        "model_text": "<URL_DOMAIN:youtu.be>",
        "labels": ["SAFE"],
        "primary_label": "SAFE",
        "severity": 0,
        "source": "real_safe",
        "decision_action": "IGNORE",
    }

    updated = ModerationExportRelabeler().relabel_row(row)

    assert updated["labels"] == ["URL"]
    assert updated["primary_label"] == "URL"
    assert updated["severity"] == 1
    assert updated["severity_multiplier"] == 0.5
    assert updated["source"] == "real_moderated"
    assert updated["decision_action"] == "REVIEW"


def test_relabel_row_uses_priority_for_invite_and_scam() -> None:
    row = {
        "model_text": "получи 5000 руб тут <DISCORD_INVITE>",
        "labels": ["SAFE"],
        "primary_label": "SAFE",
        "severity": 0,
    }

    updated = ModerationExportRelabeler().relabel_row(row)

    assert updated["primary_label"] == "SCAM"
    assert set(updated["labels"]) == {"SCAM", "INVITE", "URL"}
    assert updated["severity"] == 4


def test_relabel_row_encodes_rubert_split_multihot() -> None:
    schema = RuBertLabelSchema(labels=[ModerationLabel.SAFE, ModerationLabel.URL, ModerationLabel.SPAM])
    row = {
        "text": "@everyone <URL_DOMAIN:example.com>",
        "label_names": ["SAFE"],
        "labels": [1.0, 0.0, 0.0],
        "primary_label": "SAFE",
        "severity": 0,
    }

    updated = ModerationExportRelabeler(schema).relabel_row(row)

    assert updated["label_names"] == ["SPAM", "URL"]
    assert updated["labels"] == [0.0, 1.0, 1.0]
    assert updated["primary_label"] == "SPAM"


def test_relabel_row_marks_veiled_family_sexual_harassment_as_nsfw() -> None:
    row = {
        "model_text": "ты уважаешь свою маму? а я люблю ей давать в рот",
        "labels": ["SAFE"],
        "primary_label": "SAFE",
        "severity": 0,
    }

    updated = ModerationExportRelabeler().relabel_row(row)

    assert updated["primary_label"] == "NSFW"
    assert set(updated["labels"]) == {"NSFW"}
    assert updated["severity"] == 4


def test_relabel_row_keeps_family_home_context_safe() -> None:
    row = {
        "model_text": "твоя сестренка была у меня дома, мы вместе делали проект",
        "labels": ["SAFE"],
        "primary_label": "SAFE",
        "severity": 0,
    }

    updated = ModerationExportRelabeler().relabel_row(row)

    assert updated["primary_label"] == "SAFE"
    assert updated["labels"] == ["SAFE"]
    assert updated["severity"] == 0


def test_relabel_row_marks_suspicious_money_url_as_scam() -> None:
    row = {
        "model_text": "<URL> хей ребята тут раздача бабла",
        "labels": ["SAFE"],
        "primary_label": "SAFE",
        "severity": 0,
    }

    updated = ModerationExportRelabeler().relabel_row(row)

    assert updated["primary_label"] == "SCAM"
    assert set(updated["labels"]) == {"SCAM", "URL"}


def test_relabel_row_adds_profanity_and_politics_labels() -> None:
    row = {
        "model_text": "".join(map(chr, (1047, 1077, 1083, 1077, 1085, 1089, 1082, 1080, 1081, 32, 1093, 1091, 1077, 1075, 1083, 1086, 1090, 1080, 1082))),
        "labels": ["SAFE"],
        "primary_label": "SAFE",
        "severity": 0,
    }

    updated = ModerationExportRelabeler().relabel_row(row)

    assert updated["primary_label"] == "POLITICS_IRL"
    assert set(updated["labels"]) == {"PROFANITY", "POLITICS_IRL"}


def test_relabel_row_keeps_official_steamcommunity_profile_as_url() -> None:
    row = {
        "model_text": "страница профиля steamcommunity.com/profiles/123 без подарков и входа",
        "labels": ["URL"],
        "primary_label": "URL",
        "severity": 1,
    }

    updated = ModerationExportRelabeler().relabel_row(row)

    assert updated["primary_label"] == "URL"
    assert updated["labels"] == ["URL"]
