from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.rubert.rubert_model_preparer import RuBertModelPreparer
from src.training.rubert.rubert_training_config import RuBertTrainingConfig


def main() -> None:
    config = RuBertTrainingConfig.load()
    path = RuBertModelPreparer(config).download_base_model()
    print(f"Downloaded {config.model.base_model_name} to {Path(path).resolve()}")


if __name__ == "__main__":
    main()
