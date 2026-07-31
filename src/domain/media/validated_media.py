from pydantic import BaseModel, ConfigDict, Field


class ValidatedMedia(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attachment_id: str
    analysis_bytes: bytes
    detected_mime: str = Field(max_length=127)
    file_size: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fingerprint_luma: bytes = Field(min_length=1, max_length=1_024)
    validation_latency_ms: int = Field(ge=0)

