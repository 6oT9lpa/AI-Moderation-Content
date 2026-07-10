from __future__ import annotations

from src.contracts.image_attachment_input_schema import ImageAttachmentInputSchema
from src.domain.media.image_metadata import ImageMetadata
from src.infrastructure.logging import get_logger
from src.infrastructure.media.pillow_image_rasterizer import PillowImageRasterizer

logger = get_logger(__name__)


class ImageMetadataExtractor:
    SCREENSHOT_RATIOS = (16 / 9, 4 / 3, 3 / 2, 9 / 16)

    def __init__(self, rasterizer: PillowImageRasterizer | None = None) -> None:
        self._rasterizer = rasterizer or PillowImageRasterizer()

    def extract(self, attachment: ImageAttachmentInputSchema) -> ImageMetadata:
        dimensions = self._rasterizer.inspect(attachment.image_bytes)
        width = attachment.width or (dimensions[0] if dimensions else None)
        height = attachment.height or (dimensions[1] if dimensions else None)
        aspect_ratio = round(width / height, 4) if width and height else None
        actual_file_size = len(attachment.image_bytes)
        if attachment.file_size is not None and actual_file_size and attachment.file_size != actual_file_size:
            logger.warning(
                "Image metadata size mismatch attachment_id=%s declared_size=%s actual_size=%s",
                attachment.attachment_id,
                attachment.file_size,
                actual_file_size,
            )
        file_size = actual_file_size or attachment.file_size
        metadata = ImageMetadata(
            file_name=attachment.file_name,
            content_type=attachment.content_type,
            file_size=file_size,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            is_screenshot_like=self._is_screenshot_like(width, height, aspect_ratio),
        )
        logger.info(
            "Image metadata extracted attachment_id=%s width=%s height=%s screenshot_like=%s",
            attachment.attachment_id,
            width,
            height,
            metadata.is_screenshot_like,
        )
        return metadata

    def _is_screenshot_like(self, width: int | None, height: int | None, aspect_ratio: float | None) -> bool:
        if width is None or height is None or aspect_ratio is None or width * height < 230_400:
            return False
        return any(abs(aspect_ratio - ratio) <= 0.04 for ratio in self.SCREENSHOT_RATIOS)
