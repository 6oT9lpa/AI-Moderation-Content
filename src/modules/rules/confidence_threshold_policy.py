from pydantic import BaseModel, ConfigDict, Field


class ConfidenceThresholdPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    default_min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    per_source_min_confidence: dict[str, float] = Field(default_factory=dict)
    per_label_min_confidence: dict[str, float] = Field(default_factory=dict)
