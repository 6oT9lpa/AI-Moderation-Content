import asyncio
from pathlib import Path

import pytest

from src.domain.media.ocr_input import OcrInput
from src.domain.media.ocr_runtime_config import OcrRuntimeConfig
from src.infrastructure.media.ocr_text_processor import OcrTextProcessor
from src.infrastructure.media.paddle_ocr_provider import PaddleOcrProvider
from scripts.media.compute_ocr_model_checksum import calculate_bundle_checksum


class _Prediction:
    json = {
        "res": {
            "rec_texts": ["casino bonus", "приз"],
            "rec_scores": [0.8, 0.6],
            "rec_polys": [((0, 0), (10, 0), (10, 5), (0, 5)), ((0, 6), (8, 6), (8, 10), (0, 10))],
        }
    }


class _Engine:
    def __init__(self) -> None:
        self.predict_calls = 0

    def predict(self, _pixels):
        self.predict_calls += 1
        return [_Prediction()]


@pytest.mark.asyncio
async def test_provider_uses_paddle_v3_predict_and_preserves_lines(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    engine = _Engine()
    provider = PaddleOcrProvider(
        runtime_config=runtime,
        semaphore=asyncio.Semaphore(1),
        text_processor=OcrTextProcessor(8_000),
        engine_factory=lambda _config: engine,
    )

    result = await provider.analyze(
        OcrInput(
            attachment_id="a1",
            image_bytes=_png_bytes(),
            sha256="0" * 64,
            width=1,
            height=1,
        )
    )

    assert engine.predict_calls == 1
    assert result.text == "casino bonus\nприз"
    assert result.confidence == pytest.approx(0.7)
    assert result.lines[0].bounds[2] == (10.0, 5.0)


def test_provider_rejects_model_checksum_mismatch(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path).model_copy(update={"model_checksum": "0" * 64})

    provider = PaddleOcrProvider(
        runtime_config=runtime,
        semaphore=asyncio.Semaphore(1),
        text_processor=OcrTextProcessor(8_000),
        engine_factory=lambda _config: _Engine(),
    )

    assert provider.ready is False


def _runtime(tmp_path: Path) -> OcrRuntimeConfig:
    det = tmp_path / "det"
    rec = tmp_path / "rec"
    det.mkdir()
    rec.mkdir()
    (det / "inference.json").write_text("det", encoding="utf-8")
    (rec / "inference.json").write_text("rec", encoding="utf-8")
    return OcrRuntimeConfig(
        detection_model_dir=det,
        recognition_model_dir=rec,
        device="cpu",
        cpu_threads=2,
        enable_mkldnn=False,
        inference_concurrency=1,
        timeout_seconds=5.0,
        model_checksum=calculate_bundle_checksum(det, rec),
    )


def _png_bytes() -> bytes:
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
        "0000000c49444154789c6360f8cfc0000003010100c9fe92ef0000000049454e44ae426082"
    )
