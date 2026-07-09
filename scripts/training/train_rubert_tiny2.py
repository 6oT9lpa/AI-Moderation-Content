from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.rubert.rubert_training_config import RuBertTrainingConfig

DATASET_DIR = Path("data/exports/rubert_moderation_v1")
TRAINED_OUTPUT_DIR = Path("models/rubert-tiny2-moderation-trained")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _build_dataset(rows: list[dict[str, Any]], tokenizer: Any, *, max_length: int) -> Any:
    from datasets import Dataset

    dataset = Dataset.from_list(
        [
            {
                "text": row["text"],
                "labels": [float(value) for value in row["labels"]],
            }
            for row in rows
        ]
    )

    def tokenize(batch: dict[str, list[Any]]) -> dict[str, Any]:
        tokenized = tokenizer(
            batch["text"],
            truncation=True,
            padding="max_length",
            max_length=max_length,
        )
        tokenized["labels"] = batch["labels"]
        return tokenized

    return dataset.map(tokenize, batched=True, remove_columns=["text"])


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def _compute_metrics(threshold: float) -> Any:
    from sklearn.metrics import f1_score

    def compute(eval_pred: Any) -> dict[str, float]:
        logits, labels = eval_pred
        predictions = (_sigmoid(np.asarray(logits)) >= threshold).astype(int)
        targets = np.asarray(labels).astype(int)
        return {
            "micro_f1": float(f1_score(targets, predictions, average="micro", zero_division=0)),
            "macro_f1": float(f1_score(targets, predictions, average="macro", zero_division=0)),
            "exact_match": float(np.all(predictions == targets, axis=1).mean()),
        }

    return compute


def _calculate_pos_weight(rows: list[dict[str, Any]], *, max_weight: float = 12.0) -> list[float]:
    labels = np.asarray([row["labels"] for row in rows], dtype=np.float32)
    positives = labels.sum(axis=0)
    negatives = labels.shape[0] - positives
    weights = negatives / np.maximum(positives, 1.0)
    return np.clip(weights, 1.0, max_weight).astype(np.float32).tolist()


class WeightedMultiLabelTrainer:
    @staticmethod
    def build(pos_weight: list[float]) -> type:
        import torch
        from transformers import Trainer

        class _Trainer(Trainer):
            def compute_loss(
                self,
                model: Any,
                inputs: dict[str, Any],
                return_outputs: bool = False,
                num_items_in_batch: Any | None = None,
            ) -> Any:
                labels = inputs.pop("labels")
                outputs = model(**inputs)
                weight_tensor = torch.tensor(pos_weight, dtype=outputs.logits.dtype, device=outputs.logits.device)
                loss_function = torch.nn.BCEWithLogitsLoss(pos_weight=weight_tensor)
                loss = loss_function(outputs.logits, labels.to(outputs.logits.dtype))
                return (loss, outputs) if return_outputs else loss

        return _Trainer


def train(
    *,
    dataset_dir: Path,
    output_dir: Path,
    dry_run: bool = False,
    epochs: float | None = None,
    max_steps: int = -1,
    resume_from_checkpoint: Path | None = None,
) -> None:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, TrainingArguments

    config = RuBertTrainingConfig.load()
    model_source = config.model.classifier_output_dir
    if not model_source.exists():
        model_source = config.model.local_base_dir

    train_rows = _load_jsonl(dataset_dir / "train.jsonl")
    validation_rows = _load_jsonl(dataset_dir / "validation.jsonl")
    if dry_run:
        train_rows = train_rows[:64]
        validation_rows = validation_rows[:64]

    tokenizer = AutoTokenizer.from_pretrained(model_source, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_source,
        num_labels=config.label_schema.num_labels,
        id2label=config.label_schema.id2label,
        label2id=config.label_schema.label2id,
        problem_type=config.model.problem_type,
        local_files_only=True,
        use_safetensors=True,
    )

    train_dataset = _build_dataset(train_rows, tokenizer, max_length=config.model.max_length)
    eval_dataset = _build_dataset(validation_rows, tokenizer, max_length=config.model.max_length)
    pos_weight = _calculate_pos_weight(train_rows)
    trainer_class = WeightedMultiLabelTrainer.build(pos_weight)

    args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=config.training.train_batch_size,
        per_device_eval_batch_size=config.training.eval_batch_size,
        gradient_accumulation_steps=config.training.gradient_accumulation_steps,
        learning_rate=config.training.learning_rate,
        num_train_epochs=1 if dry_run else (epochs if epochs is not None else config.training.num_train_epochs),
        max_steps=max_steps,
        warmup_ratio=config.training.warmup_ratio,
        weight_decay=config.training.weight_decay,
        fp16=config.training.fp16,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="steps",
        logging_steps=25,
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        report_to=[],
    )

    trainer = trainer_class(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        compute_metrics=_compute_metrics(config.training.threshold),
    )
    trainer.train(resume_from_checkpoint=str(resume_from_checkpoint) if resume_from_checkpoint else None)
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    (output_dir / "class_weights.json").write_text(
        json.dumps(
            {
                "pos_weight": {
                    label: weight for label, weight in zip(config.label_schema.label2id, pos_weight)
                },
                "max_weight": 12.0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved trained model to {output_dir.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune ruBERT tiny2 moderation classifier.")
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=TRAINED_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Train on a tiny subset for a smoke check.")
    parser.add_argument("--epochs", type=float, default=None, help="Override config training.num_train_epochs.")
    parser.add_argument("--max-steps", type=int, default=-1, help="Stop after N optimizer steps; -1 disables.")
    parser.add_argument("--resume-from-checkpoint", type=Path, default=None, help="Resume Trainer state from a checkpoint.")
    args = parser.parse_args()

    train(
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        epochs=args.epochs,
        max_steps=args.max_steps,
        resume_from_checkpoint=args.resume_from_checkpoint,
    )


if __name__ == "__main__":
    main()
