from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.datasets.moderation_export_relabeler import ModerationExportRelabeler
from src.training.rubert.rubert_training_config import RuBertTrainingConfig


DEFAULT_PATHS = (
    Path("data/exports/project_training_examples.jsonl"),
    Path("data/exports/rubert_moderation_v1/train.jsonl"),
    Path("data/exports/rubert_moderation_v1/validation.jsonl"),
    Path("data/exports/rubert_moderation_v1/test.jsonl"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Relabel exported moderation JSONL datasets.")
    parser.add_argument("paths", nargs="*", type=Path, default=list(DEFAULT_PATHS))
    parser.add_argument("--config", default="configs/training/rubert_tiny2.yaml")
    args = parser.parse_args()

    config = RuBertTrainingConfig.load(args.config)
    relabeler = ModerationExportRelabeler(config.label_schema)
    stats = []
    for path in args.paths:
        if not path.exists():
            continue
        stats.append(relabeler.relabel_file(path).as_dict())

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
