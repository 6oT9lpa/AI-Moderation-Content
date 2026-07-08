from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.moderation.moderation_label import ModerationLabel
from src.modules.preprocessing.rules.preprocessing_rule_policy import PreprocessingRulePolicy


class PreprocessingSpamPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mass_mentions: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.SPAM,),
            severity=2,
            confidence=0.74,
            reason="mass_mentions_detected",
            risk_weight=25,
            threshold=5,
        ),
    )
    caps: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.SPAM,),
            severity=1,
            confidence=0.58,
            reason="caps_ratio_threshold_exceeded",
            risk_weight=10,
            threshold=0.75,
            minimum_text_length=8,
        ),
    )
    emoji: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.SPAM,),
            severity=1,
            confidence=0.52,
            reason="emoji_ratio_threshold_exceeded",
            risk_weight=8,
            threshold=0.35,
            minimum_text_length=4,
        ),
    )
    repeated_chars: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.SPAM,),
            severity=1,
            confidence=0.56,
            reason="repeated_char_score_threshold_exceeded",
            risk_weight=10,
            threshold=0.4,
            minimum_text_length=6,
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _merge_rule_defaults(cls, data: object) -> object:
        if not isinstance(data, Mapping):
            return data

        merged = dict(data)

        for field_name in ("mass_mentions", "caps", "emoji", "repeated_chars"):
            field_value = merged.get(field_name)

            if isinstance(field_value, Mapping):
                default_policy = cls.model_fields[field_name].get_default(call_default_factory=True)
                merged[field_name] = {
                    **default_policy.model_dump(mode="python"),
                    **field_value,
                }

        return merged

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "PreprocessingSpamPolicy":
        if not isinstance(data, Mapping):
            return cls()

        return cls.model_validate(data)
