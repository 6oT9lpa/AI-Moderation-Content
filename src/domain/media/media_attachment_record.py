from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.domain.media.media_hashes import MediaHashes


class MediaAttachmentRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: int = Field(gt=0)
    guild_id: str = Field(min_length=1, max_length=32)
    attachment_id: str = Field(min_length=1, max_length=128)
    file_name: str | None = Field(default=None, max_length=255)
    declared_mime: str = Field(max_length=127)
    detected_mime: str | None = Field(default=None, max_length=127)
    file_size: int = Field(ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    hashes: MediaHashes | None = None
    screenshot_like: bool = False
    redacted_ocr_text: str | None = Field(default=None, max_length=8_000)
    ocr_language: str | None = Field(default=None, max_length=16)
    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    ocr_text_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    ocr_flags: tuple[str, ...] = Field(default=(), max_length=32)
    known_hash_match: bool = False
    storage_uri: str | None = Field(default=None, max_length=2_048)
    retention_until: datetime

