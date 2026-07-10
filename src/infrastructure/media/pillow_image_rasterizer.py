from __future__ import annotations

from io import BytesIO
from warnings import catch_warnings, simplefilter

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class PillowImageRasterizer:
    def __init__(self, *, max_image_pixels: int = 20_000_000) -> None:
        self._max_image_pixels = max_image_pixels

    def inspect(self, image_bytes: bytes) -> tuple[int, int] | None:
        if not image_bytes:
            return None
        try:
            from PIL import Image

            with catch_warnings():
                simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(image_bytes)) as image:
                    dimensions = image.size
                    if not self._is_safe_size(*dimensions):
                        return None
            logger.debug("Media stage=image_metadata status=decoded width=%s height=%s", *dimensions)
            return dimensions
        except Exception as exc:
            logger.warning("Media stage=image_metadata status=failed error_type=%s", type(exc).__name__)
            return None

    def rasterize(self, image_bytes: bytes, width: int, height: int) -> tuple[tuple[int, ...], ...] | None:
        if not image_bytes:
            return None
        try:
            from PIL import Image

            with catch_warnings():
                simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(image_bytes)) as image:
                    if not self._is_safe_size(*image.size):
                        return None
                    grayscale = image.convert("L").resize((width, height))
                    pixels = tuple(
                        tuple(grayscale.getpixel((x, y)) for x in range(width))
                        for y in range(height)
                    )
            logger.debug("Media stage=image_rasterize status=completed width=%s height=%s", width, height)
            return pixels
        except Exception as exc:
            logger.warning("Media stage=image_rasterize status=failed error_type=%s", type(exc).__name__)
            return None

    def _is_safe_size(self, width: int, height: int) -> bool:
        image_pixels = width * height
        if image_pixels <= self._max_image_pixels:
            return True
        logger.warning(
            "Media stage=image_validation status=rejected reason=pixel_limit width=%s height=%s pixels=%s max_pixels=%s",
            width,
            height,
            image_pixels,
            self._max_image_pixels,
        )
        return False
