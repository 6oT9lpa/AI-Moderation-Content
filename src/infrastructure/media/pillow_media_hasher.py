import asyncio
import hashlib

import numpy as np

from src.application.ports.media.media_hasher import MediaHasher
from src.domain.media.downloaded_media import DownloadedMedia
from src.domain.media.media_hashes import MediaHashes
from src.domain.media.validated_media import ValidatedMedia


class PillowMediaHasher(MediaHasher):
    async def calculate(self, downloaded: DownloadedMedia, validated: ValidatedMedia) -> MediaHashes:
        return await asyncio.to_thread(self._calculate_sync, downloaded, validated)

    def _calculate_sync(self, downloaded: DownloadedMedia, validated: ValidatedMedia) -> MediaHashes:
        pixels = np.frombuffer(validated.fingerprint_luma, dtype=np.uint8).reshape((32, 32))
        return MediaHashes(
            sha256=hashlib.sha256(downloaded.content).hexdigest(),
            phash=self._phash(pixels),
            dhash=self._dhash(pixels),
            ahash=self._ahash(pixels),
        )

    @staticmethod
    def _bits_to_hex(bits: np.ndarray) -> str:
        value = 0
        for bit in bits.flatten():
            value = (value << 1) | int(bool(bit))
        return f"{value:016x}"

    def _ahash(self, pixels: np.ndarray) -> str:
        sample = pixels.reshape(8, 4, 8, 4).mean(axis=(1, 3))
        return self._bits_to_hex(sample >= sample.mean())

    def _dhash(self, pixels: np.ndarray) -> str:
        sample = pixels[:8, :9]
        return self._bits_to_hex(sample[:, 1:] >= sample[:, :-1])

    def _phash(self, pixels: np.ndarray) -> str:
        values = pixels.astype(np.float64)
        indices = np.arange(32)
        transform = np.cos((2 * indices[:, None] + 1) * indices[None, :] * np.pi / 64.0)
        transform[:, 0] /= np.sqrt(2.0)
        dct = transform.T @ values @ transform
        low_frequency = dct[:8, :8]
        median = np.median(low_frequency.flatten()[1:])
        return self._bits_to_hex(low_frequency >= median)

