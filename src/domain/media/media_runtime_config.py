from pydantic import BaseModel, ConfigDict, Field


class MediaRuntimeConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool
    required: bool
    max_attachments: int = Field(ge=1, le=10)
    max_file_size_bytes: int = Field(gt=0)
    max_total_size_bytes: int = Field(gt=0)
    max_width: int = Field(gt=0)
    max_height: int = Field(gt=0)
    max_pixels: int = Field(gt=0)
    retention_hours: int = Field(ge=1, le=720)
    hash_cache_ttl_hours: int = Field(ge=1, le=720)
    input_version: str = Field(min_length=1, max_length=128)
    ocr_required: bool
    image_required: bool
