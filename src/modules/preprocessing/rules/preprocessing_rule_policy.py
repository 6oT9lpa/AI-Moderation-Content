from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.moderation.moderation_label import ModerationLabel


class PreprocessingRulePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool
    labels: tuple[ModerationLabel, ...]
    severity: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)
    risk_weight: int = Field(ge=0)
    threshold: float | None = Field(default=None, ge=0.0)
    minimum_text_length: int = Field(default=0, ge=0)

    @field_validator("labels", mode="before")
    @classmethod
    def _parse_labels(cls, value: object) -> tuple[ModerationLabel, ...] | list[object]:
        if isinstance(value, str):
            return tuple(
                ModerationLabel(label.strip())
                for label in value.split(",")
                if label.strip()
            )

        return value

    def merge(self, data: Mapping[str, Any] | None) -> "PreprocessingRulePolicy":
        if not isinstance(data, Mapping):
            return self

        merged = {
            **self.model_dump(mode="python"),
            **data,
        }
        return PreprocessingRulePolicy.model_validate(merged)
