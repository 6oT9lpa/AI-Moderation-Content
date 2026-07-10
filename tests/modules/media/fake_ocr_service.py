from __future__ import annotations

from src.contracts.image_attachment_input_schema import ImageAttachmentInputSchema
from src.domain.media.ocr_result import OcrResult
from src.infrastructure.logging import get_logger

logger = get_logger("tests.media")


class FakeOcrService:
    def __init__(self, result: OcrResult) -> None:
        self._result = result

    async def extract(self, attachment: ImageAttachmentInputSchema) -> OcrResult:
        logger.info(
            "Fake OCR extracted attachment_id=%s text_length=%s language=%s confidence=%s",
            attachment.attachment_id,
            len(self._result.text),
            self._result.language,
            self._result.confidence,
        )
        return self._result
