from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_IMAGE_ATTACHMENT_BYTES = 8 * 1024 * 1024


class ImageAttachmentInputSchema(BaseModel):
    """A platform adapter's neutral representation of an image attachment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attachment_id: str
    content_type: str
    file_name: str | None = None
    file_size: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    storage_uri: str | None = None
    image_bytes: bytes = Field(
        default=b"",
        exclude=True,
        repr=False,
        max_length=MAX_IMAGE_ATTACHMENT_BYTES,
    )

    @field_validator("content_type")
    @classmethod
    def validate_image_content_type(cls, value: str) -> str:
        normalized_value = value.lower().strip()
        if not normalized_value.startswith("image/"):
            raise ValueError("content_type must describe an image")
        return normalized_value
