from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.moderation.moderation_label import ModerationLabel
from src.modules.preprocessing.rules.preprocessing_rule_policy import PreprocessingRulePolicy


class PreprocessingFloodPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    messages_10s: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.FLOOD,),
            severity=3,
            confidence=0.82,
            reason="too_many_messages_in_10s",
            risk_weight=35,
            threshold=4,
        ),
    )
    messages_60s: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.FLOOD,),
            severity=3,
            confidence=0.86,
            reason="too_many_messages_in_60s",
            risk_weight=45,
            threshold=12,
        ),
    )
    repeated_messages_10m: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.FLOOD,),
            severity=3,
            confidence=0.78,
            reason="same_text_repeated_in_window",
            risk_weight=35,
            threshold=3,
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _merge_rule_defaults(cls, data: object) -> object:
        if not isinstance(data, Mapping):
            return data

        merged = dict(data)

        for field_name in ("messages_10s", "messages_60s", "repeated_messages_10m"):
            field_value = merged.get(field_name)

            if isinstance(field_value, Mapping):
                default_policy = cls.model_fields[field_name].get_default(call_default_factory=True)
                merged[field_name] = {
                    **default_policy.model_dump(mode="python"),
                    **field_value,
                }

        return merged

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "PreprocessingFloodPolicy":
        if not isinstance(data, Mapping):
            return cls()

        return cls.model_validate(data)
