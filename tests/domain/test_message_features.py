from __future__ import annotations

from src.domain import MessageFeatures


def test_message_features_to_dict_serializes_all_fields() -> None:
    features = MessageFeatures(
        text_length=10,
        word_count=2,
        line_count=1,
        url_count=1,
        invite_count=1,
        mention_count=1,
        role_mention_count=0,
        channel_mention_count=0,
        emoji_count=0,
        uppercase_ratio=0.5,
        digit_ratio=0.1,
        punctuation_count=1,
        punctuation_ratio=0.1,
        newline_count=0,
        unique_chars=8,
        spaces_count=1,
        average_word_length=4.5,
        longest_word_length=5,
        repeated_char_score=0.0,
        has_repeated_chars=False,
        has_url=True,
        has_invite=True,
        has_shortener=False,
        has_zero_width=False,
        has_cyrillic=True,
        has_latin=True,
        has_mixed_scripts=True,
        has_suspicious_unicode=False,
    )

    data = features.to_dict()

    assert data["text_length"] == 10
    assert data["has_invite"] is True
    assert data["has_mixed_scripts"] is True
    assert set(data) == {
        "text_length",
        "word_count",
        "line_count",
        "url_count",
        "invite_count",
        "mention_count",
        "role_mention_count",
        "channel_mention_count",
        "emoji_count",
        "uppercase_ratio",
        "digit_ratio",
        "punctuation_count",
        "punctuation_ratio",
        "newline_count",
        "unique_chars",
        "spaces_count",
        "average_word_length",
        "longest_word_length",
        "repeated_char_score",
        "has_repeated_chars",
        "has_url",
        "has_invite",
        "has_shortener",
        "has_zero_width",
        "has_cyrillic",
        "has_latin",
        "has_mixed_scripts",
        "has_suspicious_unicode",
    }
