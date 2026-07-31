"""Prepare and run the pinned MIT YOLO trainer outside the application environment."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SOURCE_REPOSITORY = "https://github.com/MultimediaTechLab/YOLO.git"
SOURCE_COMMIT = "c4cb5f6f56102eceeaa7d75e23e1125cd0373eaf"


def prepare_checkout(checkout: Path) -> None:
    if not checkout.exists():
        subprocess.run(["git", "clone", SOURCE_REPOSITORY, str(checkout)], check=True)
    subprocess.run(["git", "-C", str(checkout), "fetch", "origin", SOURCE_COMMIT], check=True)
    subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", SOURCE_COMMIT], check=True)
    actual = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if actual != SOURCE_COMMIT:
        raise RuntimeError("MIT YOLO checkout does not match the pinned commit")
    if not (checkout / "LICENSE").read_text(encoding="utf-8").startswith("MIT License"):
        raise RuntimeError("MIT YOLO checkout has an unexpected license")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--dataset-config", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--model", default="v9-s")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if not args.dataset_config.is_file():
        raise FileNotFoundError(f"dataset config is missing: {args.dataset_config}")
    prepare_checkout(args.checkout.resolve())
    if args.prepare_only:
        return
    subprocess.run(
        [
            sys.executable,
            str(args.checkout.resolve() / "yolo" / "lazy.py"),
            "task=train",
            f"task.data.batch_size={args.batch_size}",
            f"model={args.model}",
            f"dataset={args.dataset_config.resolve()}",
            f"device={args.device}",
        ],
        cwd=args.checkout.resolve(),
        check=True,
    )


if __name__ == "__main__":
    main()
