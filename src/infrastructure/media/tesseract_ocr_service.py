from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from shutil import which
from time import perf_counter
from warnings import catch_warnings, simplefilter

from src.contracts.image_attachment_input_schema import ImageAttachmentInputSchema
from src.domain.media.ocr_result import OcrResult
from src.domain.media.ocr_status import OcrStatus
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class TesseractOcrService:
    def __init__(
        self,
        *,
        languages: str = "rus+eng",
        timeout_seconds: int = 10,
        max_image_pixels: int = 20_000_000,
        max_text_length: int = 20_000,
        executable_path: str | Path | None = None,
    ) -> None:
        self._languages = languages
        self._timeout_seconds = timeout_seconds
        self._max_image_pixels = max_image_pixels
        self._max_text_length = max_text_length
        self._executable_path = self._resolve_executable_path(executable_path)
        if self._executable_path is None:
            logger.warning("Media stage=ocr status=unavailable reason=tesseract_executable_not_found")
        else:
            logger.info(
                "Media stage=ocr status=initialized languages=%s timeout_seconds=%s executable=%s",
                languages,
                timeout_seconds,
                self._executable_path,
            )

    async def extract(self, attachment: ImageAttachmentInputSchema) -> OcrResult:
        return await asyncio.to_thread(self._extract_sync, attachment)

    def _extract_sync(self, attachment: ImageAttachmentInputSchema) -> OcrResult:
        started_at = perf_counter()
        if not attachment.image_bytes:
            return self._log_result(
                attachment.attachment_id,
                OcrResult(status=OcrStatus.SKIPPED, error="missing_image_bytes"),
                started_at,
            )
        if self._executable_path is None:
            return self._log_result(
                attachment.attachment_id,
                OcrResult(status=OcrStatus.FAILED, error="tesseract_executable_not_found"),
                started_at,
            )
        try:
            import pytesseract
            from PIL import Image

            pytesseract.pytesseract.tesseract_cmd = str(self._executable_path)
            with catch_warnings():
                simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(attachment.image_bytes)) as image:
                    width, height = image.size
                    if width * height > self._max_image_pixels:
                        return self._log_result(
                            attachment.attachment_id,
                            OcrResult(status=OcrStatus.FAILED, error="image_pixel_limit_exceeded"),
                            started_at,
                        )
                    data = pytesseract.image_to_data(
                        image,
                        lang=self._languages,
                        output_type=pytesseract.Output.DICT,
                        timeout=self._timeout_seconds,
                    )
            words = [str(word).strip() for word in data["text"] if str(word).strip()]
            text = " ".join(words)[: self._max_text_length]
            confidences = [
                float(value) / 100
                for value in data["conf"]
                if str(value).replace(".", "", 1).lstrip("-").isdigit() and float(value) >= 0
            ]
            return self._log_result(
                attachment.attachment_id,
                OcrResult(
                    text=text,
                    language=self._languages,
                    confidence=round(sum(confidences) / len(confidences), 4) if confidences else None,
                    status=OcrStatus.COMPLETED,
                ),
                started_at,
            )
        except Exception as exc:
            logger.warning(
                "Media stage=ocr status=failed attachment_id=%s error_type=%s",
                attachment.attachment_id,
                type(exc).__name__,
            )
            return self._log_result(
                attachment.attachment_id,
                OcrResult(status=OcrStatus.FAILED, error=f"ocr_failed:{type(exc).__name__}"),
                started_at,
            )

    def _log_result(self, attachment_id: str, result: OcrResult, started_at: float) -> OcrResult:
        logger.info(
            "Media stage=ocr status=%s attachment_id=%s text_length=%s confidence=%s latency_ms=%s error=%s",
            result.status.value,
            attachment_id,
            len(result.text),
            result.confidence,
            round((perf_counter() - started_at) * 1000),
            result.error,
        )
        return result

    def _resolve_executable_path(self, configured_path: str | Path | None) -> Path | None:
        executable_from_path = which("tesseract")
        candidates = [
            Path(configured_path) if configured_path is not None else None,
            Path(executable_from_path) if executable_from_path else None,
            Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
        ]
        return next((candidate for candidate in candidates if candidate is not None and candidate.is_file()), None)
