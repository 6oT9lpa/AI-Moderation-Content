from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable

from src.domain.media.image_hashes import ImageHashes
from src.infrastructure.logging import get_logger
from src.infrastructure.media.pillow_image_rasterizer import PillowImageRasterizer

logger = get_logger(__name__)


class ImageHashCalculator:
    def __init__(self, rasterizer: PillowImageRasterizer | None = None) -> None:
        self._rasterizer = rasterizer or PillowImageRasterizer()

    def calculate(self, image_bytes: bytes) -> ImageHashes:
        if not image_bytes:
            logger.warning("Media stage=image_hash status=skipped reason=missing_image_bytes")
            return ImageHashes()
        sha256 = hashlib.sha256(image_bytes).hexdigest()
        pixels = self._rasterizer.rasterize(image_bytes, 32, 32)
        if pixels is None:
            return ImageHashes(sha256=sha256)
        hashes = ImageHashes(
            sha256=sha256,
            phash=self._perceptual_hash(pixels),
            dhash=self._difference_hash(pixels),
            ahash=self._average_hash(pixels),
        )
        logger.info("Media stage=image_hash status=completed sha256=%s phash=%s", hashes.sha256, hashes.phash)
        return hashes

    def _average_hash(self, pixels: tuple[tuple[int, ...], ...]) -> str:
        sampled = self._resample(pixels, 8, 8)
        average = sum(sum(row) for row in sampled) / 64
        return self._bits_to_hex(value >= average for row in sampled for value in row)

    def _difference_hash(self, pixels: tuple[tuple[int, ...], ...]) -> str:
        sampled = self._resample(pixels, 9, 8)
        return self._bits_to_hex(
            sampled[row][column] > sampled[row][column + 1]
            for row in range(8)
            for column in range(8)
        )

    def _perceptual_hash(self, pixels: tuple[tuple[int, ...], ...]) -> str:
        coefficients: list[float] = []
        size = len(pixels)
        for vertical in range(8):
            for horizontal in range(8):
                value = sum(
                    pixels[y][x]
                    * math.cos((2 * x + 1) * horizontal * math.pi / (2 * size))
                    * math.cos((2 * y + 1) * vertical * math.pi / (2 * size))
                    for y in range(size)
                    for x in range(size)
                )
                coefficients.append(value)
        median = sorted(coefficients[1:])[len(coefficients[1:]) // 2]
        return self._bits_to_hex(value >= median for value in coefficients)

    def _resample(
        self,
        pixels: tuple[tuple[int, ...], ...],
        width: int,
        height: int,
    ) -> tuple[tuple[int, ...], ...]:
        source_height = len(pixels)
        source_width = len(pixels[0])
        return tuple(
            tuple(
                pixels[min(int(y * source_height / height), source_height - 1)][
                    min(int(x * source_width / width), source_width - 1)
                ]
                for x in range(width)
            )
            for y in range(height)
        )

    def _bits_to_hex(self, bits: Iterable[bool]) -> str:
        bit_text = "".join("1" if bit else "0" for bit in bits)
        return f"{int(bit_text, 2):016x}"
