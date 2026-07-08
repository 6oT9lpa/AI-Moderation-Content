from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.moderation.moderation_label import ModerationLabel
from src.modules.preprocessing.rules.preprocessing_rule_policy import PreprocessingRulePolicy


class PreprocessingLinkPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detect_any_url: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.URL,),
            severity=1,
            confidence=0.55,
            reason="url_detected",
            risk_weight=10,
        ),
    )
    shortener: PreprocessingRulePolicy = Field(
        default_factory=lambda: PreprocessingRulePolicy(
            enabled=True,
            labels=(ModerationLabel.URL, ModerationLabel.SPAM),
            severity=2,
            confidence=0.68,
            reason="url_shortener_detected",
            risk_weight=20,
        ),
    )
    allowed_domains: tuple[str, ...] = (
        "youtube.com",
        "youtu.be",
        "tiktok.com",
        "vm.tiktok.com",
    )
    shortener_domains: tuple[str, ...] = (
        "bit.ly",
        "t.co",
        "tinyurl.com",
        "goo.gl",
        "cutt.ly",
        "is.gd",
        "s.id",
        "clck.ru",
        "vk.cc",
        "ow.ly",
        "shorturl.at",
        "rebrand.ly",
    )

    @model_validator(mode="before")
    @classmethod
    def _merge_rule_defaults(cls, data: object) -> object:
        if not isinstance(data, Mapping):
            return data

        merged = dict(data)

        for field_name in ("detect_any_url", "shortener"):
            field_value = merged.get(field_name)

            if isinstance(field_value, Mapping):
                default_policy = cls.model_fields[field_name].get_default(call_default_factory=True)
                merged[field_name] = {
                    **default_policy.model_dump(mode="python"),
                    **field_value,
                }

        return merged

    @field_validator("allowed_domains", "shortener_domains", mode="before")
    @classmethod
    def _parse_domains(cls, value: object) -> tuple[str, ...] | object:
        if isinstance(value, str):
            raw_domains = [item.strip() for item in value.split(",") if item.strip()]
        elif isinstance(value, list | tuple | set | frozenset):
            raw_domains = [str(item).strip() for item in value if str(item).strip()]
        else:
            return value

        return tuple(dict.fromkeys(domain.lower().removeprefix("www.") for domain in raw_domains))

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "PreprocessingLinkPolicy":
        if not isinstance(data, Mapping):
            return cls()

        return cls.model_validate(data)
