from __future__ import annotations

import asyncio
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from time import perf_counter
from collections.abc import Mapping

import numpy as np
from PIL import Image

from src.application.media_error import MediaInferenceError, MediaModelUnavailableError
from src.application.ports.media.ocr_provider import OcrProvider
from src.domain.media.ocr_input import OcrInput
from src.domain.media.ocr_line import OcrLine
from src.domain.media.ocr_result import OcrResult
from src.domain.media.ocr_runtime_config import OcrRuntimeConfig
from src.infrastructure.logging import get_logger
from src.infrastructure.media.ocr_text_processor import OcrTextProcessor
from scripts.media.compute_ocr_model_checksum import calculate_bundle_checksum

logger = get_logger(__name__)


class PaddleOcrProvider(OcrProvider):
    def __init__(
        self,
        *,
        runtime_config: OcrRuntimeConfig,
        semaphore: asyncio.Semaphore,
        text_processor: OcrTextProcessor,
        engine_factory: Callable[[OcrRuntimeConfig], object] | None = None,
    ) -> None:
        self._runtime_config = runtime_config
        self._semaphore = semaphore
        self._text_processor = text_processor
        self._engine: object | None = None
        self._load_error: str | None = None
        try:
            self._verify_model_checksum(runtime_config)
            self._engine = (engine_factory or self._build_engine)(runtime_config)
            logger.info(
                "OCR model loaded model_name=pp-ocrv5-mobile-eslav model_version=%s device=%s threads=%s",
                self.model_version,
                runtime_config.device,
                runtime_config.cpu_threads,
            )
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
        return f"{package_version}:{self._runtime_config.model_checksum[:12]}"[:128]

    async def analyze(self, input_image: OcrInput) -> OcrResult:
        if self._engine is None:
            raise MediaModelUnavailableError("OCR model is unavailable")
        started_at = perf_counter()
        try:
            async with self._semaphore:
                raw_lines = await asyncio.wait_for(
                    asyncio.to_thread(self._infer_sync, input_image.image_bytes),
                    timeout=self._runtime_config.timeout_seconds,
                )
        except asyncio.TimeoutError as exc:
            raise MediaInferenceError("OCR inference timed out") from exc
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise MediaInferenceError("OCR inference failed") from exc

        text = "\n".join(line.text for line in raw_lines)
        confidence = sum(line.confidence for line in raw_lines) / len(raw_lines) if raw_lines else None
        processed = self._text_processor.process(text)
        return OcrResult(
            attachment_id=input_image.attachment_id,
            lines=tuple(raw_lines),
            text=processed.normalized_text,
            redacted_text=processed.redacted_text,
            text_hash=processed.text_hash,
            language=processed.language,
            confidence=confidence,
            model_name="pp-ocrv5-mobile-eslav",
            model_version=self.model_version,
            processing_time_ms=round((perf_counter() - started_at) * 1_000),
            flags=processed.flags,
        )

    def _infer_sync(self, image_bytes: bytes) -> list[OcrLine]:
        with Image.open(BytesIO(image_bytes)) as image:
            pixels = np.asarray(image.convert("RGB"))
        engine = self._engine
        if engine is None:
            raise MediaModelUnavailableError("OCR model is unavailable")
        raw_result = engine.predict(pixels)
        lines: list[OcrLine] = []
        for page in raw_result or ():
            payload = self._result_payload(page)
            texts = payload.get("rec_texts", ())
            scores = payload.get("rec_scores", ())
            polygons = payload.get("rec_polys", payload.get("dt_polys", ()))
            for index, text in enumerate(texts):
                score = float(scores[index]) if index < len(scores) else 0.0
                polygon = polygons[index] if index < len(polygons) else ()
                bounds = tuple((float(point[0]), float(point[1])) for point in polygon)
                lines.append(OcrLine(text=str(text), confidence=max(0.0, min(1.0, score)), bounds=bounds))
        return lines

    @staticmethod
    def _result_payload(result: object) -> Mapping:
        if isinstance(result, Mapping):
            nested = result.get("res")
            return nested if isinstance(nested, Mapping) else result
        json_payload = getattr(result, "json", None)
        if isinstance(json_payload, Mapping):
            nested = json_payload.get("res")
            return nested if isinstance(nested, Mapping) else json_payload
        raise ValueError("PaddleOCR returned an unsupported result")

    @staticmethod
    def _build_engine(runtime_config: OcrRuntimeConfig) -> object:
        from paddleocr import PaddleOCR

        return PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_detection_model_dir=str(runtime_config.detection_model_dir),
            text_recognition_model_name="eslav_PP-OCRv5_mobile_rec",
            text_recognition_model_dir=str(runtime_config.recognition_model_dir),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device=runtime_config.device,
            cpu_threads=runtime_config.cpu_threads,
            enable_mkldnn=runtime_config.enable_mkldnn,
        )

    @staticmethod
    def _verify_model_checksum(runtime_config: OcrRuntimeConfig) -> None:
        actual_checksum = calculate_bundle_checksum(
            runtime_config.detection_model_dir,
            runtime_config.recognition_model_dir,
        )
        if actual_checksum != runtime_config.model_checksum:
            raise ValueError("OCR model checksum mismatch")
