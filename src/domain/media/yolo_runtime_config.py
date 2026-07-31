from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class YoloRuntimeConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    model_dir: Path
    device: str = Field(pattern=r"^(cpu|cuda)$")
    inference_concurrency: int = Field(strict=True, ge=1, le=8)
    timeout_seconds: float = Field(strict=True, gt=0.0, le=120.0)
    confidence_threshold: float = Field(strict=True, ge=0.0, le=1.0)
    iou_threshold: float = Field(strict=True, ge=0.0, le=1.0)
    max_detections: int = Field(strict=True, ge=1, le=256)

    @model_validator(mode="after")
    def require_model_bundle(self) -> "YoloRuntimeConfig":
        if not self.model_dir.is_dir():
            raise ValueError("YOLO model directory is missing")
        for file_name in ("model.onnx", "manifest.json"):
            if not (self.model_dir / file_name).is_file():
                raise ValueError(f"YOLO model bundle is missing {file_name}")
        return self
