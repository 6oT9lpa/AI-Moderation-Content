from __future__ import annotations

import re
import string

from src.domain import MessageFeatures
from src.modules.preprocessing.text_normalizer import TextNormalizer

_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+", re.UNICODE)
_EMOJI_RANGES = (
    (0x1F300, 0x1FAFF),
    (0x2600, 0x26FF),
    (0x2700, 0x27BF),
)


class TextFeatureExtractor:
    PUNCTUATION = set(string.punctuation)

    @classmethod
    def extract(
        cls,
        text: str,
        *,
        urls: tuple[str, ...] = (),
        invites: tuple[str, ...] = (),
        has_shortener: bool = False,
        mention_count: int = 0,
        role_mention_count: int = 0,
        channel_mention_count: int = 0,
    ) -> MessageFeatures:
        text = text or ""
        text_length = len(text)
        words = _WORD_RE.findall(text)
        word_count = len(words)

        letters = 0
        uppercase = 0
        digits = 0
        punctuation = 0
        emoji_count = 0
        longest_repeat = 1
        current_repeat = 1
        previous_char = ""

        has_cyrillic = False
        has_latin = False

        for char in text:
            if char.isalpha():
                letters += 1

                if char.isupper():
                    uppercase += 1

                code = ord(char)

                if 0x0400 <= code <= 0x04FF:
                    has_cyrillic = True
                elif "A" <= char <= "Z" or "a" <= char <= "z":
                    has_latin = True

                if char.casefold() == previous_char.casefold():
                    current_repeat += 1
                    longest_repeat = max(longest_repeat, current_repeat)
                else:
                    current_repeat = 1

                previous_char = char
            else:
                current_repeat = 1
                previous_char = ""

            if char.isdigit():
                digits += 1

            if char in cls.PUNCTUATION:
                punctuation += 1

            if cls._is_emoji(char):
                emoji_count += 1

        uppercase_ratio = uppercase / letters if letters else 0.0
        digit_ratio = digits / text_length if text_length else 0.0
        punctuation_ratio = punctuation / text_length if text_length else 0.0
        repeated_char_score = min(max(longest_repeat - 1, 0) / 10, 1.0)

        return MessageFeatures(
            text_length=text_length,
            word_count=word_count,
            line_count=text.count("\n") + 1 if text else 0,
            url_count=len(urls),
            invite_count=len(invites),
            mention_count=mention_count,
            role_mention_count=role_mention_count,
            channel_mention_count=channel_mention_count,
            emoji_count=emoji_count,
            uppercase_ratio=round(uppercase_ratio, 3),
            digit_ratio=round(digit_ratio, 3),
            punctuation_count=punctuation,
            punctuation_ratio=round(punctuation_ratio, 3),
            newline_count=text.count("\n"),
            unique_chars=len(set(text)),
            spaces_count=text.count(" "),
            average_word_length=round(sum(len(word) for word in words) / word_count, 2)
            if word_count
            else 0.0,
            longest_word_length=max((len(word) for word in words), default=0),
            repeated_char_score=round(repeated_char_score, 3),
            has_repeated_chars=longest_repeat >= 3,
            has_url=bool(urls),
            has_invite=bool(invites),
            has_shortener=has_shortener,
            has_zero_width=TextNormalizer.contains_zero_width(text),
            has_cyrillic=has_cyrillic,
            has_latin=has_latin,
            has_mixed_scripts=has_cyrillic and has_latin,
            has_suspicious_unicode=TextNormalizer.has_suspicious_unicode(text),
        )

    @staticmethod
    def _is_emoji(char: str) -> bool:
        code = ord(char)
        return any(start <= code <= end for start, end in _EMOJI_RANGES)
