from __future__ import annotations

import asyncio
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image

from src.application.media_error import MediaInferenceError, MediaModelUnavailableError
from src.application.ports.media.ocr_provider import OcrProvider
from src.domain.media.ocr_input import OcrInput
from src.domain.media.ocr_result import OcrResult
from src.infrastructure.logging import get_logger
from src.infrastructure.media.ocr_text_processor import OcrTextProcessor

logger = get_logger(__name__)


class PaddleOcrProvider(OcrProvider):
    def __init__(
        self,
        *,
        model_dir: Path,
        semaphore: asyncio.Semaphore,
        timeout_seconds: float,
        text_processor: OcrTextProcessor,
        engine_factory: Callable[[Path], object] | None = None,
    ) -> None:
        self._model_dir = model_dir
        self._semaphore = semaphore
        self._timeout_seconds = timeout_seconds
        self._text_processor = text_processor
        self._engine: object | None = None
        self._load_error: str | None = None
        try:
            self._engine = (engine_factory or self._build_engine)(model_dir)
            logger.info("OCR model loaded model_name=paddleocr-ru-en model_version=%s", self.model_version)
        except Exception as exc:
            self._load_error = type(exc).__name__
            logger.warning("OCR model is unavailable error_type=%s", self._load_error)

    @property
    def ready(self) -> bool:
        return self._engine is not None

    @property
    def enabled(self) -> bool:
        return True

    @property
    def model_version(self) -> str:
        try:
            package_version = version("paddleocr")
        except PackageNotFoundError:
            package_version = "unknown"
        return f"{package_version}:{self._model_dir.name}"[:128]

    async def analyze(self, input_image: OcrInput) -> OcrResult:
        if self._engine is None:
            raise MediaModelUnavailableError("OCR model is unavailable")
        started_at = perf_counter()
        try:
            async with self._semaphore:
                raw_lines = await asyncio.wait_for(
                    asyncio.to_thread(self._infer_sync, input_image.image_bytes),
                    timeout=self._timeout_seconds,
                )
        except asyncio.TimeoutError as exc:
            raise MediaInferenceError("OCR inference timed out") from exc
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise MediaInferenceError("OCR inference failed") from exc

        text = "\n".join(line_text for line_text, _ in raw_lines)
        confidence = sum(score for _, score in raw_lines) / len(raw_lines) if raw_lines else None
        processed = self._text_processor.process(text)
        return OcrResult(
            attachment_id=input_image.attachment_id,
            text=processed.normalized_text,
            redacted_text=processed.redacted_text,
            text_hash=processed.text_hash,
            language=processed.language,
            confidence=confidence,
            model_name="paddleocr-ru-en",
            model_version=self.model_version,
            processing_time_ms=round((perf_counter() - started_at) * 1_000),
            flags=processed.flags,
        )

    def _infer_sync(self, image_bytes: bytes) -> list[tuple[str, float]]:
        with Image.open(BytesIO(image_bytes)) as image:
            pixels = np.asarray(image.convert("RGB"))
        engine = self._engine
        if engine is None:
            raise MediaModelUnavailableError("OCR model is unavailable")
        raw_result = engine.ocr(pixels, cls=True)
        lines: list[tuple[str, float]] = []
        for page in raw_result or ():
            for line in page or ():
                if not isinstance(line, (list, tuple)) or len(line) < 2:
                    continue
                recognition = line[1]
                if isinstance(recognition, (list, tuple)) and len(recognition) >= 2:
                    lines.append((str(recognition[0]), max(0.0, min(1.0, float(recognition[1])))))
        return lines

    @staticmethod
    def _build_engine(model_dir: Path) -> object:
        if not model_dir.is_dir():
            raise FileNotFoundError("OCR model directory is missing")
        from paddleocr import PaddleOCR

        return PaddleOCR(
            lang="ru",
            use_angle_cls=True,
            show_log=False,
            det_model_dir=str(model_dir / "det"),
            rec_model_dir=str(model_dir / "rec"),
            cls_model_dir=str(model_dir / "cls"),
        )

