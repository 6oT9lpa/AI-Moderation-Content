from pydantic import BaseModel, ConfigDict, Field


class ActionThresholdPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    IGNORE: float = Field(default=0.0, ge=0.0, le=100.0)
    LOG: float = Field(default=10.0, ge=0.0, le=100.0)
    REVIEW: float = Field(default=40.0, ge=0.0, le=100.0)
    WARN: float = Field(default=50.0, ge=0.0, le=100.0)
    DELETE: float = Field(default=70.0, ge=0.0, le=100.0)
    DELETE_WARN: float = Field(default=80.0, ge=0.0, le=100.0)
    TIMEOUT: float = Field(default=90.0, ge=0.0, le=100.0)
    BAN: float = Field(default=95.0, ge=0.0, le=100.0)
