from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.domain.message_features import MessageFeatures
from src.infrastructure.logging import get_logger

logger = get_logger("tests.preprocessing")


def _make_features() -> MessageFeatures:
    return MessageFeatures(
        text_length=42,
        token_count=5,
        word_count=5,
        line_count=1,
        url_count=1,
        invite_count=1,
        mention_count=2,
        role_mention_count=1,
        channel_mention_count=1,
        emoji_count=1,
        emoji_ratio=0.024,
        uppercase_ratio=0.25,
        digit_ratio=0.1,
        punctuation_count=3,
        punctuation_ratio=0.071,
        newline_count=0,
        unique_chars=20,
        spaces_count=4,
        average_word_length=5.2,
        longest_word_length=10,
        repeated_char_score=0.3,
        has_repeated_chars=True,
        duplicate_text_score=0.5,
        recent_user_messages_10s=2,
        recent_user_messages_60s=4,
        recent_user_messages_10m=8,
        repeated_messages_10m=2,
        message_interval_seconds=1.25,
        has_url=True,
        has_invite=True,
        has_shortener=False,
        has_zero_width=False,
        has_cyrillic=True,
        has_latin=True,
        has_mixed_scripts=True,
        has_suspicious_unicode=False,
    )


def test_message_features_to_dict_contains_all_fields() -> None:
    features = _make_features()
    data = features.to_dict()

    logger.info(
        "MessageFeatures to_dict checked keys=%s url_count=%s invite_count=%s",
        len(data),
        data["url_count"],
        data["invite_count"],
    )

    assert data["text_length"] == 42
    assert data["token_count"] == 5
    assert data["word_count"] == 5
    assert data["url_count"] == 1
    assert data["invite_count"] == 1
    assert data["has_mixed_scripts"] is True
    assert data["has_repeated_chars"] is True
    assert data["repeated_messages_10m"] == 2


def test_message_features_is_frozen() -> None:
    features = _make_features()

    logger.info("MessageFeatures frozen validation text_length=%s", features.text_length)

    with pytest.raises(FrozenInstanceError):
        features.text_length = 100  # type: ignore[misc]
