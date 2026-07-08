from pydantic import BaseModel, ConfigDict, Field


class RiskScorePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    min: float = Field(default=0.0, ge=0.0)
    max: float = Field(default=100.0, le=100.0)
