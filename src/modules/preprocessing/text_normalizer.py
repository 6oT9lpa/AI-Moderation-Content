from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH_RE = re.compile(r"[\u200B\u200C\u200D\u200E\u200F\u2060\uFEFF]")
_SPACES_RE = re.compile(r"\s+")
_REPEAT_RE = re.compile(r"(.)\1{2,}")


class TextNormalizer:
    @staticmethod
    def normalize(text: str, *, collapse_repeats: bool = True) -> str:
        if not text:
            return ""

        normalized = unicodedata.normalize("NFKC", text)
        normalized = normalized.casefold()
        normalized = _ZERO_WIDTH_RE.sub("", normalized)
        normalized = _SPACES_RE.sub(" ", normalized).strip()

        if collapse_repeats:
            normalized = _REPEAT_RE.sub(r"\1\1", normalized)

        return normalized

    @staticmethod
    def contains_zero_width(text: str) -> bool:
        return bool(_ZERO_WIDTH_RE.search(text or ""))

    @staticmethod
    def has_suspicious_unicode(text: str) -> bool:
        for char in text or "":
            category = unicodedata.category(char)

            if category in {"Cf", "Cc"} and char not in {"\n", "\r", "\t"}:
                return True

        return False

    @staticmethod
    def detect_scripts(text: str) -> tuple[bool, bool]:
        has_cyrillic = False
        has_latin = False

        for char in text or "":
            code = ord(char)

            if 0x0400 <= code <= 0x04FF:
                has_cyrillic = True
            elif "A" <= char <= "Z" or "a" <= char <= "z":
                has_latin = True

        return has_cyrillic, has_latin
