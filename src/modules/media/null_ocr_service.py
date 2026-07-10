from __future__ import annotations

from src.contracts.image_attachment_input_schema import ImageAttachmentInputSchema
from src.domain.media.ocr_result import OcrResult
from src.domain.media.ocr_status import OcrStatus
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class NullOcrService:
    async def extract(self, attachment: ImageAttachmentInputSchema) -> OcrResult:
        logger.info("OCR skipped attachment_id=%s reason=no_ocr_service_configured", attachment.attachment_id)
        return OcrResult(
            status=OcrStatus.SKIPPED,
            error="no_ocr_service_configured",
        )
