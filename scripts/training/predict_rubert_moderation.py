from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.rubert.rubert_training_config import RuBertTrainingConfig
from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_label_priority import resolve_primary_label
from src.training.datasets.training_text_sanitizer import TrainingTextSanitizer

DEFAULT_MODEL_DIR = Path("models/rubert-tiny2-moderation-trained")
DEFAULT_TEXTS = [
    "\u043f\u0440\u0438\u0432\u0435\u0442, \u043a\u0430\u043a \u0434\u0435\u043b\u0430?",
    "\u0437\u0430\u0445\u043e\u0434\u0438 https://discord.gg/testcode",
    "\u0442\u044b \u0438\u0434\u0438\u043e\u0442",
    "https://cdn.discordapp.com/attachments/1/2/image.gif",
    "\u043f\u043e\u043b\u0443\u0447\u0438 5000 \u0440\u0443\u0431 \u043f\u0440\u044f\u043c\u043e \u0441\u0435\u0439\u0447\u0430\u0441",
]


def _load_thresholds(model_dir: Path, labels: list[str], fallback: float) -> dict[str, float]:
    path = model_dir / "thresholds.json"
    if not path.exists():
        return {label: fallback for label in labels}

    data = json.loads(path.read_text(encoding="utf-8"))
    return {label: float(data.get(label, fallback)) for label in labels}


def predict(
    *,
    model_dir: Path,
    texts: list[str],
    threshold: float | None = None,
    sanitize: bool = True,
    use_thresholds_file: bool = False,
) -> list[dict]:
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

    config = RuBertTrainingConfig.load()
    sanitizer = TrainingTextSanitizer()
    model_texts = [sanitizer.sanitize(text) for text in texts] if sanitize else texts
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()

    batch = tokenizer(
        model_texts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=config.model.max_length,
    ).to(device)

    with torch.inference_mode():
        logits = model(**batch).logits
        probabilities = torch.sigmoid(logits).detach().cpu().tolist()

    id2label = {int(index): label for index, label in model.config.id2label.items()}
    label_order = [id2label[index] for index in range(len(id2label))]
    thresholds = (
        _load_thresholds(model_dir, label_order, config.training.threshold)
        if use_thresholds_file and threshold is None
        else {label: float(config.training.threshold if threshold is None else threshold) for label in label_order}
    )
    rows: list[dict] = []
    for raw_text, model_text, scores in zip(texts, model_texts, probabilities):
        ranked = sorted(
            (
                {
                    "label": id2label[index],
                    "score": round(float(score), 6),
                }
                for index, score in enumerate(scores)
            ),
            key=lambda item: item["score"],
            reverse=True,
        )
        selected = [item for item in ranked if item["score"] >= thresholds[item["label"]]]
        if any(item["label"] != ModerationLabel.SAFE.value for item in selected):
            selected = [item for item in selected if item["label"] != ModerationLabel.SAFE.value]
        selected_label_values = [item["label"] for item in selected]
        primary_label = resolve_primary_label(
            [ModerationLabel(label) for label in selected_label_values],
            fallback=ModerationLabel.SAFE,
        )
        rows.append(
            {
                "text": raw_text,
                "model_text": model_text,
                "thresholds": thresholds,
                "selected_labels": selected_label_values,
                "primary_label": primary_label.value,
                "top_labels": ranked[:5],
            }
        )

    print(f"device={device}")
    print(f"model_dir={model_dir.resolve()}")
    return rows


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Run inference with trained ruBERT moderation classifier.")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--use-thresholds-file", action="store_true")
    parser.add_argument("--no-sanitize", action="store_true", help="Feed texts as-is instead of using training sanitizer.")
    parser.add_argument("texts", nargs="*", help="Texts to classify. Uses built-in smoke examples when omitted.")
    args = parser.parse_args()

    texts = args.texts or DEFAULT_TEXTS
    rows = predict(
        model_dir=args.model_dir,
        texts=texts,
        threshold=args.threshold,
        sanitize=not args.no_sanitize,
        use_thresholds_file=args.use_thresholds_file,
    )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
