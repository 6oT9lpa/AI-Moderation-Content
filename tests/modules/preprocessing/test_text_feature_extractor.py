from __future__ import annotations

from src.modules.preprocessing import TextFeatureExtractor


def test_extract_features_counts_core_text_signals() -> None:
    text = "HELLO!!! 123 😂\nПривет"

    features = TextFeatureExtractor.extract(
        text,
        urls=("https://example.com",),
        invites=("abc123",),
        has_shortener=True,
        mention_count=2,
        role_mention_count=1,
        channel_mention_count=1,
    )

    assert features.text_length == len(text)
    assert features.word_count == 3
    assert features.line_count == 2
    assert features.newline_count == 1
    assert features.url_count == 1
    assert features.invite_count == 1
    assert features.mention_count == 2
    assert features.role_mention_count == 1
    assert features.channel_mention_count == 1
    assert features.emoji_count == 1
    assert features.punctuation_count == 3
    assert features.has_url is True
    assert features.has_invite is True
    assert features.has_shortener is True
    assert features.has_cyrillic is True
    assert features.has_latin is True
    assert features.has_mixed_scripts is True


def test_extract_features_detects_repeated_chars() -> None:
    features = TextFeatureExtractor.extract("ааааа")

    assert features.has_repeated_chars is True
    assert features.repeated_char_score == 0.4


def test_extract_features_handles_empty_text() -> None:
    features = TextFeatureExtractor.extract("")

    assert features.text_length == 0
    assert features.word_count == 0
    assert features.line_count == 0
    assert features.uppercase_ratio == 0.0
    assert features.digit_ratio == 0.0
    assert features.punctuation_ratio == 0.0
    assert features.average_word_length == 0.0
    assert features.longest_word_length == 0
    assert features.has_url is False
    assert features.has_invite is False


def test_message_features_to_dict_contains_all_expected_keys() -> None:
    features = TextFeatureExtractor.extract("Hello 123")
    data = features.to_dict()

    assert data["text_length"] == len("Hello 123")
    assert data["word_count"] == 2
    assert data["has_latin"] is True
    assert "repeated_char_score" in data
    assert "has_suspicious_unicode" in data
