from __future__ import annotations

from src.infrastructure.logging import get_logger
from src.modules.preprocessing.text_normalizer import TextNormalizer

logger = get_logger("tests.preprocessing")


def test_normalize_lowercases_removes_zero_width_and_collapses_spaces() -> None:
    text = "  HELLO\u200b     WORLD  "

    result = TextNormalizer.normalize(text)

    logger.info("Normalizer basic normalization input=%r result=%r", text, result)

    assert result == "hello world"


def test_normalize_collapses_repeated_characters_by_default() -> None:
    text = "Спаааам!!!"

    result = TextNormalizer.normalize(text)

    logger.info("Normalizer repeated characters input=%r result=%r", text, result)

    assert result == "спаам!!"


def test_normalize_can_keep_repeated_characters() -> None:
    text = "Спаааам!!!"

    result = TextNormalizer.normalize(text, collapse_repeats=False)

    logger.info("Normalizer keep repeats input=%r result=%r", text, result)

    assert result == "спаааам!!!"


def test_contains_zero_width_detects_hidden_characters() -> None:
    text = "hello\u200bworld"

    result = TextNormalizer.contains_zero_width(text)

    logger.info("Normalizer zero-width check result=%s", result)

    assert result is True


def test_has_suspicious_unicode_detects_format_characters() -> None:
    text = "safe\u2060text"

    result = TextNormalizer.has_suspicious_unicode(text)

    logger.info("Normalizer suspicious unicode check result=%s", result)

    assert result is True


def test_detect_scripts_detects_cyrillic_and_latin() -> None:
    result = TextNormalizer.detect_scripts("hello привет")

    logger.info("Normalizer script detection result=%s", result)

    assert result == (True, True)
