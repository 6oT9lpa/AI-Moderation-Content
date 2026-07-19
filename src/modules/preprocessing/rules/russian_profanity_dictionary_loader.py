from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.infrastructure.logging import get_logger
from src.modules.preprocessing.rules.preprocessing_russian_profanity_policy import (
    PreprocessingRussianProfanityPolicy,
)

logger = get_logger(__name__)


class RussianProfanityDictionaryLoader:
    """Loads separate profanity dictionaries into the preprocessing policy once."""

    def load(self, policy: PreprocessingRussianProfanityPolicy) -> PreprocessingRussianProfanityPolicy:
        obscene_words = policy.obscene_words or self._load_words(policy.obscene_dictionary_path)
        literary_words = policy.literary_words or self._load_words(policy.literary_dictionary_path)
        logger.info(
            "Russian profanity dictionaries loaded obscene_words=%s literary_words=%s",
            len(obscene_words),
            len(literary_words),
        )
        return policy.model_copy(update={"obscene_words": obscene_words, "literary_words": literary_words})

    def _load_words(self, path: str) -> tuple[str, ...]:
        dictionary_path = Path(path)
        if not dictionary_path.exists():
            logger.warning("Russian profanity dictionary is missing path=%s", dictionary_path)
            return ()

        import yaml

        data = yaml.safe_load(dictionary_path.read_text(encoding="utf-8")) or {}
        words = data.get("words") if isinstance(data, Mapping) else None
        if not isinstance(words, list):
            logger.warning("Russian profanity dictionary has invalid format path=%s", dictionary_path)
            return ()
        return tuple(str(word).casefold() for word in words if str(word).strip())
