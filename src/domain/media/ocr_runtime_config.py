from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OcrRuntimeConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    detection_model_dir: Path
    recognition_model_dir: Path
    device: str = Field(pattern=r"^cpu$")
    cpu_threads: int = Field(strict=True, ge=1, le=64)
    inference_concurrency: int = Field(strict=True, ge=1, le=8)
    timeout_seconds: float = Field(strict=True, gt=0.0, le=120.0)
    model_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def require_local_models(self) -> "OcrRuntimeConfig":
        if not self.detection_model_dir.is_dir():
            raise ValueError("OCR detection model directory is missing")
        if not self.recognition_model_dir.is_dir():
            raise ValueError("OCR recognition model directory is missing")
        return self
