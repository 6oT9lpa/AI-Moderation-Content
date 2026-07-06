from __future__ import annotations

from src.modules.preprocessing import TextNormalizer


def test_normalize_is_deterministic_and_collapses_noise() -> None:
    raw_text = "  ПРИВЕЕЕЕТ\u200b     WORLD!!!  "

    normalized = TextNormalizer.normalize(raw_text)

    assert normalized == "привеет world!!"
    assert TextNormalizer.normalize(raw_text) == normalized


def test_normalize_can_keep_repeated_characters() -> None:
    raw_text = "coooool"

    assert TextNormalizer.normalize(raw_text) == "cool"
    assert TextNormalizer.normalize(raw_text, collapse_repeats=False) == "coooool"


def test_contains_zero_width_detects_hidden_characters() -> None:
    assert TextNormalizer.contains_zero_width("hello\u200bworld") is True
    assert TextNormalizer.contains_zero_width("hello world") is False


def test_has_suspicious_unicode_detects_control_format_characters() -> None:
    assert TextNormalizer.has_suspicious_unicode("safe text") is False
    assert TextNormalizer.has_suspicious_unicode("safe\u200btext") is True


def test_detect_scripts_returns_cyrillic_and_latin_flags() -> None:
    assert TextNormalizer.detect_scripts("привет") == (True, False)
    assert TextNormalizer.detect_scripts("hello") == (False, True)
    assert TextNormalizer.detect_scripts("hello привет") == (True, True)
    assert TextNormalizer.detect_scripts("123 !!!") == (False, False)
