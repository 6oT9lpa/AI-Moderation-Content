from pydantic import BaseModel, ConfigDict, Field


class OcrLine(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(max_length=8_000)
    confidence: float = Field(ge=0.0, le=1.0)
    bounds: tuple[tuple[float, float], ...] = Field(default=(), max_length=16)
