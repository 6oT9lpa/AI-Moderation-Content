from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.moderation.moderation_label import ModerationLabel
from src.modules.preprocessing.rules.preprocessing_rule_policy import PreprocessingRulePolicy


class PreprocessingSemanticPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hate_keywords: tuple[str, ...] = ()
    nsfw_keywords: tuple[str, ...] = ()
    profanity_terms: tuple[str, ...] = ()
    politics_keywords: tuple[str, ...] = ()
    hate: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.HATE,),
            severity=5,
            confidence=0.82,
            reason="hate_keyword_detected",
            risk_weight=60,
        ),
    )
    nsfw: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.NSFW,),
            severity=4,
            confidence=0.82,
            reason="nsfw_keyword_detected",
            risk_weight=70,
        ),
    )
    profanity: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.PROFANITY,),
            severity=1,
            confidence=0.94,
            reason="russian_profanity_detected",
            risk_weight=8,
        ),
    )
    politics: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.POLITICS_IRL,),
            severity=2,
            confidence=0.9,
            reason="real_world_politics_detected",
            risk_weight=18,
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _merge_rule_defaults(cls, data: object) -> object:
        if not isinstance(data, Mapping):
            return data

        merged = dict(data)
        for rule_name in ("hate", "nsfw", "profanity", "politics"):
            rule_data = merged.get(rule_name)
            if isinstance(rule_data, Mapping):
                default_policy = cls.model_fields[rule_name].get_default(call_default_factory=True)
                merged[rule_name] = {
                    **default_policy.model_dump(mode="python"),
                    **rule_data,
                }
        return merged

    @field_validator("hate_keywords", "nsfw_keywords", "profanity_terms", "politics_keywords", mode="before")
    @classmethod
    def _parse_keywords(cls, value: object) -> tuple[str, ...] | object:
        if isinstance(value, str):
            raw_keywords = [item.strip() for item in value.split(",") if item.strip()]
        elif isinstance(value, list | tuple | set | frozenset):
            raw_keywords = [str(item).strip() for item in value if str(item).strip()]
        else:
            return value

        return tuple(dict.fromkeys(keyword.casefold() for keyword in raw_keywords))
