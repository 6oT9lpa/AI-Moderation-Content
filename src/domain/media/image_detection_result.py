from pydantic import BaseModel, ConfigDict, Field

from src.domain.media.image_detection import ImageDetection


class ImageDetectionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attachment_id: str
    detections: tuple[ImageDetection, ...] = Field(default=(), max_length=256)
    model_name: str = Field(max_length=128)
    model_version: str = Field(max_length=128)
    processing_time_ms: int = Field(ge=0)
    warnings: tuple[str, ...] = Field(default=(), max_length=16)

