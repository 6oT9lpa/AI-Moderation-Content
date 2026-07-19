from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from src.modules.preprocessing.rules.preprocessing_blacklist_words_policy import (
    PreprocessingBlacklistWordsPolicy,
)
from src.modules.preprocessing.rules.preprocessing_evasion_policy import PreprocessingEvasionPolicy
from src.modules.preprocessing.rules.preprocessing_flood_policy import PreprocessingFloodPolicy
from src.modules.preprocessing.rules.preprocessing_invite_policy import PreprocessingInvitePolicy
from src.modules.preprocessing.rules.preprocessing_link_policy import PreprocessingLinkPolicy
from src.modules.preprocessing.rules.preprocessing_russian_profanity_policy import PreprocessingRussianProfanityPolicy
from src.modules.preprocessing.rules.preprocessing_semantic_policy import PreprocessingSemanticPolicy
from src.modules.preprocessing.rules.preprocessing_spam_policy import PreprocessingSpamPolicy


class PreprocessingRuleSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    links: PreprocessingLinkPolicy = Field(default_factory=PreprocessingLinkPolicy)
    flood: PreprocessingFloodPolicy = Field(default_factory=PreprocessingFloodPolicy)
    spam: PreprocessingSpamPolicy = Field(default_factory=PreprocessingSpamPolicy)
    blacklist_words: PreprocessingBlacklistWordsPolicy = Field(default_factory=PreprocessingBlacklistWordsPolicy)
    invite: PreprocessingInvitePolicy = Field(default_factory=PreprocessingInvitePolicy)
    evasion: PreprocessingEvasionPolicy = Field(default_factory=PreprocessingEvasionPolicy)
    semantic: PreprocessingSemanticPolicy = Field(default_factory=PreprocessingSemanticPolicy)
    russian_profanity: PreprocessingRussianProfanityPolicy = Field(default_factory=PreprocessingRussianProfanityPolicy)
    semantic_placeholders: dict[str, Any] = Field(default_factory=dict)
    new_account_link_days: int = Field(default=7, ge=0)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PreprocessingRuleSettings":
        normalized = cls._normalize_legacy_mapping(data)
        return cls.model_validate(normalized)

    @property
    def detect_any_url(self) -> bool:
        return self.links.detect_any_url.enabled

    @property
    def max_messages_10s(self) -> int:
        return int(self.flood.messages_10s.threshold or 0)

    @property
    def max_messages_60s(self) -> int:
        return int(self.flood.messages_60s.threshold or 0)

    @property
    def max_repeated_messages_10m(self) -> int:
        return int(self.flood.repeated_messages_10m.threshold or 0)

    @property
    def mass_mentions_threshold(self) -> int:
        return int(self.spam.mass_mentions.threshold or 0)

    @property
    def caps_ratio_threshold(self) -> float:
        return float(self.spam.caps.threshold or 0)

    @property
    def emoji_ratio_threshold(self) -> float:
        return float(self.spam.emoji.threshold or 0)

    @property
    def repeated_char_score_threshold(self) -> float:
        return float(self.spam.repeated_chars.threshold or 0)

    @classmethod
    def _normalize_legacy_mapping(cls, data: Mapping[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = dict(data)
        links = dict(cls._as_mapping(normalized.get("links")))
        flood = dict(cls._as_mapping(normalized.get("flood")))
        spam = dict(cls._as_mapping(normalized.get("spam")))
        semantic = dict(cls._as_mapping(normalized.get("semantic")))
        russian_profanity = dict(cls._as_mapping(normalized.get("russian_profanity")))

        if "detect_any_url" in normalized:
            detect_any_url = dict(cls._as_mapping(links.get("detect_any_url")))
            detect_any_url["enabled"] = normalized.pop("detect_any_url")
            links["detect_any_url"] = detect_any_url

        cls._move_legacy_threshold(normalized, flood, "max_messages_10s", "messages_10s")
        cls._move_legacy_threshold(normalized, flood, "max_messages_60s", "messages_60s")
        cls._move_legacy_threshold(normalized, flood, "max_repeated_messages_10m", "repeated_messages_10m")
        cls._move_legacy_threshold(normalized, spam, "mass_mentions_threshold", "mass_mentions")
        cls._move_legacy_threshold(normalized, spam, "caps_ratio_threshold", "caps")
        cls._move_legacy_threshold(normalized, spam, "emoji_ratio_threshold", "emoji")
        cls._move_legacy_threshold(normalized, spam, "repeated_char_score_threshold", "repeated_chars")
        cls._move_legacy_russian_profanity(semantic, russian_profanity)

        normalized["links"] = links
        normalized["flood"] = flood
        normalized["spam"] = spam
        normalized["semantic"] = semantic
        normalized["russian_profanity"] = russian_profanity
        return normalized

    @staticmethod
    def _move_legacy_russian_profanity(source: dict[str, Any], target: dict[str, Any]) -> None:
        """Move the former shared semantic profanity configuration to its own policy."""
        legacy_words = source.pop("profanity_terms", None)
        legacy_rule = source.pop("profanity", None)

        if legacy_words is not None and "obscene_words" not in target:
            target["obscene_words"] = legacy_words

        if legacy_rule is not None and "obscene" not in target:
            target["obscene"] = legacy_rule

    @staticmethod
    def _move_legacy_threshold(
        source: dict[str, Any],
        target: dict[str, Any],
        source_key: str,
        target_key: str,
    ) -> None:
        if source_key not in source:
            return

        policy_data = dict(PreprocessingRuleSettings._as_mapping(target.get(target_key)))
        policy_data["threshold"] = source.pop(source_key)
        target[target_key] = policy_data

    @staticmethod
    def _as_mapping(value: object) -> Mapping[str, Any]:
        if isinstance(value, Mapping):
            return value

        return {}
