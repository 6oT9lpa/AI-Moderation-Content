from pydantic import BaseModel, ConfigDict, Field, model_validator


class RiskScorePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    min: float = Field(default=0.0, ge=0.0)
    max: float = Field(default=100.0, le=100.0)

    @model_validator(mode="after")
    def validate_range(self) -> "RiskScorePolicy":
        if self.min > self.max:
            raise ValueError("risk_score.min must be less than or equal to risk_score.max")

        return self
