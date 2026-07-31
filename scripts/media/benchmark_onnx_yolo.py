"""Benchmark the production ONNX provider against one representative image."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import statistics
import time
from pathlib import Path

import numpy as np
from PIL import Image

from src.domain.media.image_detection_input import ImageDetectionInput
from src.domain.media.yolo_runtime_config import YoloRuntimeConfig
from src.infrastructure.media.onnx_yolo_detection_provider import OnnxYoloDetectionProvider


async def benchmark(args: argparse.Namespace) -> dict[str, object]:
    image_bytes = args.image.read_bytes()
    with Image.open(args.image) as image:
        width, height = image.size
    provider = OnnxYoloDetectionProvider(
        runtime_config=YoloRuntimeConfig(
            model_dir=args.model_dir,
            device=args.device,
            inference_concurrency=1,
            timeout_seconds=120.0,
            confidence_threshold=0.0,
            iou_threshold=1.0,
            max_detections=256,
        ),
        semaphore=asyncio.Semaphore(1),
    )
    if not provider.ready:
        raise RuntimeError("ONNX YOLO provider is not ready")
    request = ImageDetectionInput(
        attachment_id="benchmark",
        image_bytes=image_bytes,
        sha256=hashlib.sha256(image_bytes).hexdigest(),
        width=width,
        height=height,
    )
    for _ in range(args.warmup):
        await provider.analyze(request)
    samples: list[float] = []
    detections = 0
    started = time.perf_counter()
    for _ in range(args.iterations):
        iteration_started = time.perf_counter()
        result = await provider.analyze(request)
        samples.append((time.perf_counter() - iteration_started) * 1_000)
        detections = len(result.detections)
    elapsed = time.perf_counter() - started
    return {
        "schema_version": "1",
        "host": platform.node(),
        "python": platform.python_version(),
        "device_requested": args.device,
        "execution_providers": list(provider.execution_providers),
        "model_dir": str(args.model_dir.resolve()),
        "model_version": result.model_version,
        "image_sha256": request.sha256,
        "image_size": [width, height],
        "warmup": args.warmup,
        "iterations": args.iterations,
        "detections_last_run": detections,
        "latency_ms": {
            "mean": round(statistics.fmean(samples), 3),
            "p50": round(float(np.percentile(samples, 50)), 3),
            "p95": round(float(np.percentile(samples, 95)), 3),
            "max": round(max(samples), 3),
        },
        "throughput_images_per_second": round(args.iterations / elapsed, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), required=True)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.warmup < 0 or args.iterations < 1:
        parser.error("warmup must be non-negative and iterations must be positive")
    report = asyncio.run(benchmark(args))
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
