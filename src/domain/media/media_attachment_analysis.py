from pydantic import BaseModel, ConfigDict, Field

from src.domain.media.image_detection_result import ImageDetectionResult
from src.domain.media.media_attachment import MediaAttachment
from src.domain.media.media_attachment_status import MediaAttachmentStatus
from src.domain.media.media_hashes import MediaHashes
from src.domain.media.ocr_result import OcrResult


class MediaAttachmentAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attachment: MediaAttachment
    status: MediaAttachmentStatus
    detected_mime: str | None = None
    actual_file_size: int | None = Field(default=None, gt=0)
    hashes: MediaHashes | None = None
    known_hash_match: bool = False
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    ocr_result: OcrResult | None = None
    image_result: ImageDetectionResult | None = None
    warnings: tuple[str, ...] = Field(default=(), max_length=32)
    stage_latency_ms: dict[str, int] = Field(default_factory=dict)
