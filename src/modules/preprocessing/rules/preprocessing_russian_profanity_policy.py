from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.moderation.moderation_label import ModerationLabel
from src.modules.preprocessing.rules.preprocessing_rule_policy import PreprocessingRulePolicy


class PreprocessingRussianProfanityPolicy(BaseModel):
    """Policy for deterministic Russian obscenity and literary-profanity checks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    obscene_words: tuple[str, ...] = ()
    literary_words: tuple[str, ...] = ()
    obscene: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.PROFANITY,),
            severity=1,
            confidence=0.94,
            reason="russian_obscene_word_detected",
            risk_weight=8,
        ),
    )
    literary: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.PROFANITY,),
            severity=1,
            confidence=0.82,
            reason="russian_literary_profanity_detected",
            risk_weight=5,
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _merge_rule_defaults(cls, data: object) -> object:
        if not isinstance(data, Mapping):
            return data

        merged = dict(data)
        for rule_name in ("obscene", "literary"):
            rule_data = merged.get(rule_name)
            if isinstance(rule_data, Mapping):
                default_policy = cls.model_fields[rule_name].get_default(call_default_factory=True)
                merged[rule_name] = {**default_policy.model_dump(mode="python"), **rule_data}
        return merged

    @field_validator("obscene_words", "literary_words", mode="before")
    @classmethod
    def _parse_words(cls, value: object) -> tuple[str, ...] | object:
        if isinstance(value, str):
            raw_words = [item.strip() for item in value.split(",") if item.strip()]
        elif isinstance(value, list | tuple | set | frozenset):
            raw_words = [str(item).strip() for item in value if str(item).strip()]
        else:
            return value

        return tuple(dict.fromkeys(word.casefold() for word in raw_words))

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "PreprocessingRussianProfanityPolicy":
        if not isinstance(data, Mapping):
            return cls()

        return cls.model_validate(data)
