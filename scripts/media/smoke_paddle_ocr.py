from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from PIL import Image

from scripts.media.compute_ocr_model_checksum import calculate_bundle_checksum
from src.domain.media.ocr_input import OcrInput
from src.domain.media.ocr_runtime_config import OcrRuntimeConfig
from src.infrastructure.media.ocr_text_processor import OcrTextProcessor
from src.infrastructure.media.paddle_ocr_provider import PaddleOcrProvider


async def run(image_path: Path, detection_model_dir: Path, recognition_model_dir: Path, cpu_threads: int) -> None:
    checksum = calculate_bundle_checksum(detection_model_dir, recognition_model_dir)
    with Image.open(image_path) as image:
        width, height = image.size
    provider = PaddleOcrProvider(
        runtime_config=OcrRuntimeConfig(
            detection_model_dir=detection_model_dir,
            recognition_model_dir=recognition_model_dir,
            device="cpu",
            cpu_threads=cpu_threads,
            enable_mkldnn=False,
            inference_concurrency=1,
            timeout_seconds=60.0,
            model_checksum=checksum,
        ),
        semaphore=asyncio.Semaphore(1),
        text_processor=OcrTextProcessor(8_000),
    )
    result = await provider.analyze(
        OcrInput(
            attachment_id="local-smoke",
            image_bytes=image_path.read_bytes(),
            sha256="0" * 64,
            width=width,
            height=height,
        )
    )
    print(
        json.dumps(
            {
                "ready": provider.ready,
                "model_name": result.model_name,
                "model_version": result.model_version,
                "line_count": len(result.lines),
                "mean_confidence": result.confidence,
                "processing_time_ms": result.processing_time_ms,
                "text": result.text,
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local CPU PaddleOCR smoke test")
    parser.add_argument("image", type=Path)
    parser.add_argument("detection_model_dir", type=Path)
    parser.add_argument("recognition_model_dir", type=Path)
    parser.add_argument("--cpu-threads", type=int, default=4)
    args = parser.parse_args()
    asyncio.run(run(args.image, args.detection_model_dir, args.recognition_model_dir, args.cpu_threads))


if __name__ == "__main__":
    main()
