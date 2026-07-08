from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.moderation.moderation_label import ModerationLabel
from src.modules.preprocessing.rules.preprocessing_rule_policy import PreprocessingRulePolicy


class PreprocessingEvasionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    unicode: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.EVASION,),
            severity=2,
            confidence=0.64,
            reason="mixed_or_suspicious_unicode_detected",
            risk_weight=20,
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _merge_rule_defaults(cls, data: object) -> object:
        if not isinstance(data, Mapping):
            return data

        merged = dict(data)
        unicode_policy = merged.get("unicode")

        if isinstance(unicode_policy, Mapping):
            default_policy = cls.model_fields["unicode"].get_default(call_default_factory=True)
            merged["unicode"] = {
                **default_policy.model_dump(mode="python"),
                **unicode_policy,
            }

        return merged

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "PreprocessingEvasionPolicy":
        if not isinstance(data, Mapping):
            return cls()

        return cls.model_validate(data)
