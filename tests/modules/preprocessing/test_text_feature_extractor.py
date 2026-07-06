from __future__ import annotations

from src.infrastructure.logging import get_logger
from src.modules.preprocessing.text_feature_extractor import TextFeatureExtractor

logger = get_logger("tests.preprocessing")


def test_extract_returns_zero_features_for_empty_text() -> None:
    features = TextFeatureExtractor.extract("")

    logger.info("Feature extraction empty text features=%s", features.to_dict())

    assert features.text_length == 0
    assert features.word_count == 0
    assert features.line_count == 0
    assert features.uppercase_ratio == 0.0
    assert features.digit_ratio == 0.0
    assert features.punctuation_ratio == 0.0
    assert features.has_url is False
    assert features.has_invite is False


def test_extract_counts_text_features() -> None:
    text = "HELLO привет 123!!! 😀"

    features = TextFeatureExtractor.extract(
        text,
        urls=("https://example.com",),
        invites=("abc123",),
        has_shortener=False,
        mention_count=2,
        role_mention_count=1,
        channel_mention_count=1,
    )

    logger.info("Feature extraction complex text features=%s", features.to_dict())

    assert features.text_length == len(text)
    assert features.word_count == 3
    assert features.url_count == 1
    assert features.invite_count == 1
    assert features.mention_count == 2
    assert features.role_mention_count == 1
    assert features.channel_mention_count == 1
    assert features.emoji_count == 1
    assert features.punctuation_count == 3
    assert features.has_cyrillic is True
    assert features.has_latin is True
    assert features.has_mixed_scripts is True
    assert features.has_url is True
    assert features.has_invite is True


def test_extract_detects_repeated_characters() -> None:
    text = "spaaaaam"

    features = TextFeatureExtractor.extract(text)

    logger.info(
        "Feature repeated chars text=%r has_repeated=%s score=%s",
        text,
        features.has_repeated_chars,
        features.repeated_char_score,
    )

    assert features.has_repeated_chars is True
    assert features.repeated_char_score > 0


def test_extract_detects_shortener_and_zero_width() -> None:
    text = "click bit.ly/test\u200b"

    features = TextFeatureExtractor.extract(
        text,
        urls=("bit.ly/test",),
        has_shortener=True,
    )

    logger.info("Feature shortener zero-width features=%s", features.to_dict())

    assert features.has_shortener is True
    assert features.has_zero_width is True
    assert features.has_suspicious_unicode is True
