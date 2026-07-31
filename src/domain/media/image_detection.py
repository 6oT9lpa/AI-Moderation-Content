from pydantic import BaseModel, ConfigDict, Field


class ImageDetection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detector_class: str = Field(min_length=1, max_length=128)
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: tuple[float, float, float, float] | None = None

