from __future__ import annotations

import re
from types import MappingProxyType

from src.infrastructure.logging import get_logger
from src.modules.preprocessing.rules.preprocessing_russian_profanity_policy import (
    PreprocessingRussianProfanityPolicy,
)

logger = get_logger(__name__)

_TOKEN_PATTERN = re.compile(r"[\w-]+", flags=re.UNICODE)
_CYRILLIC_LETTER = r"а-яё"
_SEPARATED_CYRILLIC_RUN_PATTERN = re.compile(
    rf"(?<![{_CYRILLIC_LETTER}])(?:[{_CYRILLIC_LETTER}][\s.\-·•*_|]+){{2,}}[{_CYRILLIC_LETTER}](?![{_CYRILLIC_LETTER}])",
    flags=re.IGNORECASE | re.UNICODE,
)
_NON_CYRILLIC_PATTERN = re.compile(rf"[^{_CYRILLIC_LETTER}]+", flags=re.IGNORECASE | re.UNICODE)
_OBSCENE_STEMS = (
    "бляд",
    "еба",
    "еби",
    "ебу",
    "ёба",
    "пизд",
    "пидор",
    "пидр",
    "хуе",
    "хуй",
    "суч",
    "долбоеб",
)


class RussianProfanityDetector:
    """Matches normalized Russian tokens against precompiled hash maps."""

    def __init__(self, policy: PreprocessingRussianProfanityPolicy) -> None:
        vocabulary: dict[str, str] = {
            **{word: "literary" for word in policy.literary_words},
            **{word: "obscene" for word in policy.obscene_words},
        }
        self._add_soft_sign_typo_aliases(vocabulary)
        self._vocabulary = MappingProxyType(vocabulary)
        logger.info(
            "Russian profanity detector initialized obscene_words=%s literary_words=%s",
            len(policy.obscene_words),
            len(policy.literary_words),
        )

    def find_matches(self, text: str) -> dict[str, tuple[str, ...]]:
        """Return unique matches by category without scanning the word lists."""
        matches: dict[str, list[str]] = {"obscene": [], "literary": []}
        seen_words: set[str] = set()

        normalized_text = text.casefold()
        tokens = [
            *(_TOKEN_PATTERN.findall(normalized_text)),
            *self._separator_obfuscated_candidates(normalized_text),
        ]
        for token in tokens:
            category = self._lookup_category(token)
            if category is not None and token not in seen_words:
                matches[category].append(token)
                seen_words.add(token)

        result = {category: tuple(words) for category, words in matches.items() if words}
        logger.info(
            "Russian profanity check completed token_count=%s matched_categories=%s matched_count=%s",
            len(tokens),
            sorted(result),
            sum(len(words) for words in result.values()),
        )
        return result

    def has_separator_obfuscation(self, text: str) -> bool:
        return any(
            self._lookup_category(candidate) is not None
            for candidate in self._separator_obfuscated_candidates(text.casefold())
        )

    def _lookup_category(self, token: str) -> str | None:
        """Check a token and its prefixes without iterating over the vocabulary."""
        for length in range(len(token), 2, -1):
            category = self._vocabulary.get(token[:length])
            if category is not None:
                return category
        if any(stem in token for stem in _OBSCENE_STEMS):
            return "obscene"
        return None

    @staticmethod
    def _separator_obfuscated_candidates(text: str) -> tuple[str, ...]:
        candidates = []
        for match in _SEPARATED_CYRILLIC_RUN_PATTERN.finditer(text):
            candidate = _NON_CYRILLIC_PATTERN.sub("", match.group(0))
            if 3 <= len(candidate) <= 32:
                candidates.append(candidate)
        return tuple(dict.fromkeys(candidates))

    @staticmethod
    def _add_soft_sign_typo_aliases(vocabulary: dict[str, str]) -> None:
        for word, category in tuple(vocabulary.items()):
            if word.endswith("ь"):
                vocabulary.setdefault(f"{word[:-1]}д", category)
                vocabulary.setdefault(f"{word[:-1]}т", category)
