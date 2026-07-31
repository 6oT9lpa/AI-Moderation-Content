from __future__ import annotations

import asyncio
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image

from src.application.media_error import MediaInferenceError, MediaModelUnavailableError
from src.application.ports.media.image_detection_provider import ImageDetectionProvider
from src.domain.media.image_detection import ImageDetection
from src.domain.media.image_detection_input import ImageDetectionInput
from src.domain.media.image_detection_result import ImageDetectionResult
from src.domain.media.yolo_model_manifest import YoloModelManifest
from src.domain.media.yolo_runtime_config import YoloRuntimeConfig
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class OnnxYoloDetectionProvider(ImageDetectionProvider):
    """License-isolated YOLO runtime: only a verified ONNX artifact is loaded."""

    def __init__(
        self,
        *,
        runtime_config: YoloRuntimeConfig,
        semaphore: asyncio.Semaphore,
        session_factory: Callable[[Path, list[str]], object] | None = None,
    ) -> None:
        self._config = runtime_config
        self._semaphore = semaphore
        self._manifest: YoloModelManifest | None = None
        self._session: object | None = None
        try:
            self._manifest = YoloModelManifest.load_verified(runtime_config.model_dir)
            providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if runtime_config.device == "cuda"
                else ["CPUExecutionProvider"]
            )
            self._session = (session_factory or self._build_session)(
                runtime_config.model_dir / "model.onnx", providers
            )
            active = tuple(self._session.get_providers())
            if runtime_config.device == "cuda" and "CUDAExecutionProvider" not in active:
                raise RuntimeError("CUDAExecutionProvider is unavailable")
            logger.info(
                "YOLO ONNX model loaded model=%s version=%s device=%s providers=%s",
                self._manifest.model_name,
                self._manifest.model_version,
                runtime_config.device,
                active,
            )
        except Exception as exc:
            self._session = None
            logger.warning("YOLO ONNX model is unavailable error_type=%s", type(exc).__name__)

    @property
    def ready(self) -> bool:
        return self._session is not None

    @property
    def enabled(self) -> bool:
        return True

    @property
    def execution_providers(self) -> tuple[str, ...]:
        return tuple(self._session.get_providers()) if self._session is not None else ()

    async def analyze(self, input_image: ImageDetectionInput) -> ImageDetectionResult:
        if self._session is None or self._manifest is None:
            raise MediaModelUnavailableError("YOLO ONNX model is unavailable")
        started_at = perf_counter()
        try:
            async with self._semaphore:
                detections = await asyncio.wait_for(
                    asyncio.to_thread(self._infer_sync, input_image.image_bytes),
                    timeout=self._config.timeout_seconds,
                )
        except asyncio.TimeoutError as exc:
            raise MediaInferenceError("YOLO inference timed out") from exc
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise MediaInferenceError("YOLO inference failed") from exc
        return ImageDetectionResult(
            attachment_id=input_image.attachment_id,
            detections=tuple(detections),
            model_name=self._manifest.model_name,
            model_version=self._manifest.model_version,
            processing_time_ms=round((perf_counter() - started_at) * 1_000),
        )

    def _infer_sync(self, image_bytes: bytes) -> list[ImageDetection]:
        manifest = self._manifest
        session = self._session
        if manifest is None or session is None:
            raise MediaModelUnavailableError("YOLO ONNX model is unavailable")
        tensor, scale, pad_x, pad_y, original_width, original_height = self._prepare_image(
            image_bytes, manifest.input_size
        )
        input_name = session.get_inputs()[0].name
        raw = np.asarray(session.run(None, {input_name: tensor})[0], dtype=np.float32)
        rows = np.squeeze(raw, axis=0) if raw.ndim == 3 and raw.shape[0] == 1 else raw
        if manifest.output_transposed:
            rows = rows.T
        if rows.ndim != 2:
            raise ValueError("YOLO ONNX output must be a two-dimensional detection matrix")
        offset = 5 if manifest.output_layout == "xywh_objectness_classes" else 4
        if rows.shape[1] != offset + len(manifest.class_names):
            raise ValueError("YOLO ONNX output does not match manifest classes")
        candidates: list[tuple[int, float, np.ndarray]] = []
        for row in rows:
            class_scores = row[offset:]
            class_id = int(np.argmax(class_scores))
            confidence = float(class_scores[class_id])
            if offset == 5:
                confidence *= float(row[4])
            if confidence < self._config.confidence_threshold:
                continue
            x, y, width, height = (float(value) for value in row[:4])
            box = np.array([x - width / 2, y - height / 2, x + width / 2, y + height / 2])
            box[[0, 2]] = np.clip((box[[0, 2]] - pad_x) / scale, 0, original_width)
            box[[1, 3]] = np.clip((box[[1, 3]] - pad_y) / scale, 0, original_height)
            candidates.append((class_id, confidence, box))
        kept = self._class_aware_nms(candidates)
        return [
            ImageDetection(
                detector_class=manifest.class_names[class_id],
                confidence=confidence,
                bounding_box=tuple(float(value) for value in box),
            )
            for class_id, confidence, box in kept[: self._config.max_detections]
        ]

    @staticmethod
    def _prepare_image(image_bytes: bytes, size: int) -> tuple[np.ndarray, float, int, int, int, int]:
        with Image.open(BytesIO(image_bytes)) as source:
            image = source.convert("RGB")
            original_width, original_height = image.size
            scale = min(size / original_width, size / original_height)
            resized = image.resize((round(original_width * scale), round(original_height * scale)))
        canvas = Image.new("RGB", (size, size), (114, 114, 114))
        pad_x = (size - resized.width) // 2
        pad_y = (size - resized.height) // 2
        canvas.paste(resized, (pad_x, pad_y))
        tensor = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1)[None, ...] / 255.0
        return tensor, scale, pad_x, pad_y, original_width, original_height

    def _class_aware_nms(
        self, candidates: list[tuple[int, float, np.ndarray]]
    ) -> list[tuple[int, float, np.ndarray]]:
        kept: list[tuple[int, float, np.ndarray]] = []
        for candidate in sorted(candidates, key=lambda item: item[1], reverse=True):
            if all(
                candidate[0] != accepted[0] or self._iou(candidate[2], accepted[2]) <= self._config.iou_threshold
                for accepted in kept
            ):
                kept.append(candidate)
        return kept

    @staticmethod
    def _iou(left: np.ndarray, right: np.ndarray) -> float:
        intersection_width = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
        intersection_height = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
        intersection = intersection_width * intersection_height
        left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
        right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
        union = left_area + right_area - intersection
        return intersection / union if union else 0.0

    @staticmethod
    def _build_session(model_path: Path, providers: list[str]) -> object:
        import onnxruntime as ort

        return ort.InferenceSession(str(model_path), providers=providers)
