from __future__ import annotations

import re
import unicodedata


_ZERO_WIDTH_RE = re.compile(
    r"[\u200B\u200C\u200D\u200E\u200F\u2060\uFEFF]"
)

_SPACES_RE = re.compile(r"\s+")

_REPEAT_RE = re.compile(r"(.)\1{2,}")

class TextNormalizer:

    @staticmethod
    def normalize(text: str) -> str:
        if not text:
            return ""

        text = unicodedata.normalize("NFKC", text)

        text = text.lower()

        text = _ZERO_WIDTH_RE.sub("", text)

        text = _SPACES_RE.sub(" ", text).strip()

        text = _REPEAT_RE.sub(r"\1\1", text)

        return text

    @staticmethod
    def contains_zero_width(text: str) -> bool:
        return bool(_ZERO_WIDTH_RE.search(text))
