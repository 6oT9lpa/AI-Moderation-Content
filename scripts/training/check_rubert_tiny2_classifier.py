from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.rubert.rubert_training_config import RuBertTrainingConfig


def main() -> None:
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

    config = RuBertTrainingConfig.load()
    model_path = config.model.classifier_output_dir
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()

    batch = tokenizer(
        ["test <DISCORD_INVITE>"],
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=config.model.max_length,
    ).to(device)
    with torch.inference_mode():
        output = model(**batch)

    print(f"device={device}")
    print(f"model_path={Path(model_path).resolve()}")
    print(f"logits_shape={tuple(output.logits.shape)}")
    print(f"problem_type={model.config.problem_type}")
    print(f"num_labels={model.config.num_labels}")


if __name__ == "__main__":
    main()
