from pydantic import BaseModel, ConfigDict, Field

from src.domain.media.ocr_line import OcrLine


class OcrResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attachment_id: str
    lines: tuple[OcrLine, ...] = Field(default=(), max_length=1_024)
    text: str = Field(default="", max_length=8_000)
    redacted_text: str = Field(default="", max_length=8_000)
    text_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    language: str | None = Field(default=None, max_length=16)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    model_name: str = Field(max_length=128)
    model_version: str = Field(max_length=128)
    processing_time_ms: int = Field(ge=0)
    warnings: tuple[str, ...] = Field(default=(), max_length=16)
    flags: tuple[str, ...] = Field(default=(), max_length=32)
