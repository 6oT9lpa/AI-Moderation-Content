from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def calculate_bundle_checksum(detection_model_dir: Path, recognition_model_dir: Path) -> str:
    digest = hashlib.sha256()
    roots = (("det", detection_model_dir), ("rec", recognition_model_dir))
    files = sorted(
        (prefix, path, path.relative_to(root).as_posix())
        for prefix, root in roots
        for path in root.rglob("*")
        if path.is_file()
    )
    if not files:
        raise ValueError("OCR model directories contain no files")
    for prefix, path, relative_path in files:
        digest.update(f"{prefix}/{relative_path}\0".encode("utf-8"))
        with path.open("rb") as model_file:
            for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate the deterministic PaddleOCR model bundle checksum")
    parser.add_argument("detection_model_dir", type=Path)
    parser.add_argument("recognition_model_dir", type=Path)
    args = parser.parse_args()
    print(calculate_bundle_checksum(args.detection_model_dir, args.recognition_model_dir))


if __name__ == "__main__":
    main()
