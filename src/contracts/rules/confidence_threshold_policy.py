from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.signal_source import SignalSource


class ConfidenceThresholdPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    default_min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    per_source_min_confidence: dict[str, float] = Field(default_factory=dict)
    per_label_min_confidence: dict[str, float] = Field(default_factory=dict)

    @field_validator("per_source_min_confidence")
    @classmethod
    def validate_source_thresholds(cls, value: dict[str, float]) -> dict[str, float]:
        for source, threshold in value.items():
            SignalSource(source)

            if not 0.0 <= threshold <= 1.0:
                raise ValueError("source confidence thresholds must be between 0 and 1")

        return value

    @field_validator("per_label_min_confidence")
    @classmethod
    def validate_label_thresholds(cls, value: dict[str, float]) -> dict[str, float]:
        for label, threshold in value.items():
            ModerationLabel(label)

            if not 0.0 <= threshold <= 1.0:
                raise ValueError("label confidence thresholds must be between 0 and 1")

        return value
