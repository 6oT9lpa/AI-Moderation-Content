from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.datasets.moderation_dataset_assembler import ModerationDatasetAssembler
from src.training.datasets.moderation_dataset_mix_config import ModerationDatasetMixConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ruBERT moderation dataset JSONL splits.")
    parser.add_argument("--config", default="configs/training/dataset_mix_v1.yaml")
    parser.add_argument(
        "--allow-shortfall",
        action="store_true",
        help="Write available rows and manifest instead of failing when source quotas are not satisfied.",
    )
    args = parser.parse_args()

    config = ModerationDatasetMixConfig.load(args.config)
    manifest = ModerationDatasetAssembler(config).build(strict=not args.allow_shortfall)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
