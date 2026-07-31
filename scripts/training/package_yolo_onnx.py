"""Create the checksum-verified model bundle consumed by the API runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


SOURCE_REPOSITORY = "https://github.com/MultimediaTechLab/YOLO"
SOURCE_COMMIT = "c4cb5f6f56102eceeaa7d75e23e1125cd0373eaf"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--onnx", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--class-name", action="append", required=True)
    parser.add_argument("--input-size", type=int, default=640)
    parser.add_argument(
        "--output-layout",
        choices=("xywh_objectness_classes", "xywh_classes"),
        default="xywh_objectness_classes",
    )
    parser.add_argument("--output-transposed", action="store_true")
    args = parser.parse_args()
    if not args.onnx.is_file():
        raise FileNotFoundError(args.onnx)
    if len(set(args.class_name)) != len(args.class_name):
        raise ValueError("class names must be unique and preserve training order")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / "model.onnx"
    shutil.copy2(args.onnx, target)
    manifest = {
        "schema_version": "1",
        "model_name": args.model_name,
        "model_version": args.model_version,
        "license": "MIT",
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": SOURCE_COMMIT,
        "onnx_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "input_size": args.input_size,
        "class_names": args.class_name,
        "output_layout": args.output_layout,
        "output_transposed": args.output_transposed,
    }
    temporary = args.output_dir / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output_dir / "manifest.json")


if __name__ == "__main__":
    main()
