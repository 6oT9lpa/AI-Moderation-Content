from __future__ import annotations

import re
import string

from features import MessageFeatures

_WORD_RE = re.compile(
    r"[A-Za-zА-Яа-яЁё]+",
    re.UNICODE,
)


class FeatureExtractor:

    PUNCTUATION = set(string.punctuation)

    @classmethod
    def extract(
        cls,
        text: str,
        *,
        mentions_count: int = 0,
        role_mentions_count: int = 0,
    ) -> MessageFeatures:

        if not text:
            return MessageFeatures(
                message_length=0,
                words_count=0,
                emoji_count=0,
                mentions_count=mentions_count,
                role_mentions_count=role_mentions_count,
                caps_ratio=0.0,
                digits_ratio=0.0,
                repeated_chars=False,
                punctuation_count=0,
                punctuation_ratio=0.0,
                newline_count=0,
                unique_chars=0,
                spaces_count=0,
                average_word_length=0.0,
                longest_word=0,
                has_cyrillic=False,
                has_latin=False,
                mixed_alphabet=False,
            )

        length = len(text)

        words = _WORD_RE.findall(text)
        words_count = len(words)

        emoji_count = 0
        uppercase = 0
        letters = 0
        digits = 0
        punctuation = 0
        newline_count = text.count("\n")
        spaces_count = text.count(" ")

        repeated = False

        prev = ""
        repeat = 1

        has_cyrillic = False
        has_latin = False

        for ch in text:

            if ch.isalpha():

                letters += 1

                if ch.isupper():
                    uppercase += 1

                code = ord(ch)

                if 0x0400 <= code <= 0x04FF:
                    has_cyrillic = True

                elif ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
                    has_latin = True

                # Повторы считаем только для букв
                if ch == prev:
                    repeat += 1
                    if repeat >= 3:
                        repeated = True
                else:
                    repeat = 1

                prev = ch

            else:
                prev = ""
                repeat = 1

            if ch.isdigit():
                digits += 1

            if ch in cls.PUNCTUATION:
                punctuation += 1

            # Простое определение emoji
            if (
                0x1F300 <= ord(ch) <= 0x1FAFF
                or 0x2600 <= ord(ch) <= 0x26FF
            ):
                emoji_count += 1

        caps_ratio = uppercase / letters if letters else 0.0
        digits_ratio = digits / length if length else 0.0
        punctuation_ratio = punctuation / length if length else 0.0

        average_word_length = (
            sum(len(w) for w in words) / words_count
            if words_count
            else 0.0
        )

        longest_word = (
            max((len(w) for w in words), default=0)
        )

        return MessageFeatures(
            message_length=length,
            words_count=words_count,
            emoji_count=emoji_count,
            mentions_count=mentions_count,
            role_mentions_count=role_mentions_count,
            caps_ratio=round(caps_ratio, 3),
            digits_ratio=round(digits_ratio, 3),
            repeated_chars=repeated,
            punctuation_count=punctuation,
            punctuation_ratio=round(punctuation_ratio, 3),
            newline_count=newline_count,
            unique_chars=len(set(text)),
            spaces_count=spaces_count,
            average_word_length=round(average_word_length, 2),
            longest_word=longest_word,
            has_cyrillic=has_cyrillic,
            has_latin=has_latin,
            mixed_alphabet=has_cyrillic and has_latin,
        )