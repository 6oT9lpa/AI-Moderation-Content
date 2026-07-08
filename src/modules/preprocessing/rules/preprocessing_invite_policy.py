from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.moderation.moderation_label import ModerationLabel
from src.modules.preprocessing.rules.preprocessing_rule_policy import PreprocessingRulePolicy


class PreprocessingInvitePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detected: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.INVITE,),
            severity=3,
            confidence=0.9,
            reason="invite_like_pattern_detected",
            risk_weight=45,
        ),
    )
    allowed_invite_codes: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _merge_rule_defaults(cls, data: object) -> object:
        if not isinstance(data, Mapping):
            return data

        merged = dict(data)
        detected = merged.get("detected")

        if isinstance(detected, Mapping):
            default_policy = cls.model_fields["detected"].get_default(call_default_factory=True)
            merged["detected"] = {
                **default_policy.model_dump(mode="python"),
                **detected,
            }

        return merged

    @field_validator("allowed_invite_codes", mode="before")
    @classmethod
    def _parse_invite_codes(cls, value: object) -> tuple[str, ...] | object:
        if isinstance(value, str):
            raw_codes = [item.strip() for item in value.split(",") if item.strip()]
        elif isinstance(value, list | tuple | set | frozenset):
            raw_codes = [str(item).strip() for item in value if str(item).strip()]
        else:
            return value

        return tuple(dict.fromkeys(code.lower() for code in raw_codes))

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "PreprocessingInvitePolicy":
        if not isinstance(data, Mapping):
            return cls()

        return cls.model_validate(data)
