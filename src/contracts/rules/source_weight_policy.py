from pydantic import BaseModel, ConfigDict, Field


class SourceWeightPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    PREPROCESSING: float = Field(default=1.0, ge=0.0)
    RUBERT: float = Field(default=1.0, ge=0.0)
    QWEN: float = Field(default=1.0, ge=0.0)
    OCR: float = Field(default=1.0, ge=0.0)
    IMAGE: float = Field(default=1.0, ge=0.0)
    HISTORY: float = Field(default=1.0, ge=0.0)
    MANUAL: float = Field(default=1.0, ge=0.0)
    PHISHING: float = Field(default=1.0, ge=0.0)
