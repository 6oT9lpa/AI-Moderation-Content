from __future__ import annotations

from typing import Protocol

from src.contracts.image_attachment_input_schema import ImageAttachmentInputSchema
from src.domain.media.ocr_result import OcrResult


class OcrService(Protocol):
    async def extract(self, attachment: ImageAttachmentInputSchema) -> OcrResult:
        ...
