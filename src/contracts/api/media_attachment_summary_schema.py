from pydantic import Field

from src.contracts.api.api_model import ApiModel
from src.domain.media.media_attachment_status import MediaAttachmentStatus


class MediaAttachmentSummarySchema(ApiModel):
    attachment_id: str = Field(min_length=1, max_length=128)
    status: MediaAttachmentStatus
    detected_mime: str | None = Field(default=None, max_length=127)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    ocr_language: str | None = Field(default=None, max_length=16)
    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    labels: tuple[str, ...] = Field(default=(), max_length=16)
    warnings: tuple[str, ...] = Field(default=(), max_length=32)
    stage_latency_ms: dict[str, int] = Field(default_factory=dict)
    model_name: str | None = Field(default=None, max_length=128)
    model_version: str | None = Field(default=None, max_length=128)

