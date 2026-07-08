from pydantic import BaseModel, ConfigDict, Field


class ModelAgreementPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    agreement_bonus: float = Field(default=0.1, ge=0.0)
    disagreement_penalty: float = Field(default=0.1, ge=0.0)
    high_confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
