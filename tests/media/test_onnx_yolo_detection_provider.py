import asyncio
import hashlib
import json
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.domain.media.image_detection_input import ImageDetectionInput
from src.domain.media.yolo_runtime_config import YoloRuntimeConfig
from src.infrastructure.media.onnx_yolo_detection_provider import OnnxYoloDetectionProvider


class _Input:
    name = "images"


class _Session:
    def get_providers(self) -> list[str]:
        return ["CPUExecutionProvider"]

    def get_inputs(self) -> list[_Input]:
        return [_Input()]

    def run(self, _outputs: object, inputs: dict[str, np.ndarray]) -> list[np.ndarray]:
        assert inputs["images"].shape == (1, 3, 640, 640)
        return [
            np.array(
                [[
                    [320, 320, 200, 200, 0.90, 0.90, 0.10],
                    [322, 322, 200, 200, 0.80, 0.90, 0.10],
                    [320, 320, 200, 200, 0.95, 0.10, 0.90],
                ]],
                dtype=np.float32,
            )
        ]


def _bundle(tmp_path: Path, **manifest_overrides: object) -> Path:
    model_bytes = b"verified-onnx-placeholder"
    (tmp_path / "model.onnx").write_bytes(model_bytes)
    manifest = {
        "schema_version": "1",
        "model_name": "moderation-yolov9-s",
        "model_version": "test-v1",
        "license": "MIT",
        "source_repository": "https://github.com/MultimediaTechLab/YOLO",
        "source_commit": "c4cb5f6f56102eceeaa7d75e23e1125cd0373eaf",
        "onnx_sha256": hashlib.sha256(model_bytes).hexdigest(),
        "input_size": 640,
        "class_names": ["scam_qr", "adult_explicit"],
        "output_layout": "xywh_objectness_classes",
        "output_transposed": False,
        **manifest_overrides,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def _config(model_dir: Path, *, device: str = "cpu") -> YoloRuntimeConfig:
    return YoloRuntimeConfig(
        model_dir=model_dir,
        device=device,
        inference_concurrency=1,
        timeout_seconds=1.0,
        confidence_threshold=0.25,
        iou_threshold=0.45,
        max_detections=10,
    )


def _png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (320, 160), "white").save(output, format="PNG")
    return output.getvalue()


def test_provider_verifies_manifest_runs_onnx_and_applies_class_aware_nms(tmp_path: Path) -> None:
    provider = OnnxYoloDetectionProvider(
        runtime_config=_config(_bundle(tmp_path)),
        semaphore=asyncio.Semaphore(1),
        session_factory=lambda _path, _providers: _Session(),
    )
    result = asyncio.run(
        provider.analyze(
            ImageDetectionInput(
                attachment_id="attachment-1",
                image_bytes=_png(),
                sha256="a" * 64,
                width=320,
                height=160,
            )
        )
    )

    assert provider.ready is True
    assert [detection.detector_class for detection in result.detections] == ["adult_explicit", "scam_qr"]
    assert result.detections[0].confidence == pytest.approx(0.855, abs=0.001)
    assert result.model_name == "moderation-yolov9-s"


def test_provider_refuses_non_mit_or_checksum_mismatched_bundle(tmp_path: Path) -> None:
    provider = OnnxYoloDetectionProvider(
        runtime_config=_config(_bundle(tmp_path, license="AGPL-3.0")),
        semaphore=asyncio.Semaphore(1),
        session_factory=lambda _path, _providers: _Session(),
    )
    assert provider.ready is False


def test_cuda_configuration_requires_active_cuda_provider(tmp_path: Path) -> None:
    provider = OnnxYoloDetectionProvider(
        runtime_config=_config(_bundle(tmp_path), device="cuda"),
        semaphore=asyncio.Semaphore(1),
        session_factory=lambda _path, _providers: _Session(),
    )
    assert provider.ready is False
