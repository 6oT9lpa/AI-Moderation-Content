from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL_DIR = Path("models/rubert-tiny2-moderation-trained")
DEFAULT_DATASET_DIR = Path("data/exports/rubert_moderation_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local charts and statistics for a trained ruBERT model.")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--include-test-evaluation", action="store_true")
    return parser.parse_args()


def build_training_report(
    *,
    model_dir: Path,
    dataset_dir: Path,
    output_dir: Path | None = None,
    include_test_evaluation: bool = False,
) -> dict[str, Any]:
    state_path = _find_latest_trainer_state(model_dir)
    state = _load_json(state_path)
    output = output_dir or model_dir / "training_report"
    output.mkdir(parents=True, exist_ok=True)
    chart_dir = output / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)

    history = state.get("log_history", [])
    dataset_stats = _collect_dataset_stats(dataset_dir)
    existing_summary_path = output / "training_summary.json"
    existing_summary = _load_json(existing_summary_path) if existing_summary_path.exists() else {}
    test_evaluation = (
        _evaluate_test_split(model_dir, dataset_dir)
        if include_test_evaluation
        else existing_summary.get("test_evaluation")
    )
    chart_paths = _build_charts(history, dataset_stats, chart_dir, test_evaluation)
    summary = _build_summary(state, state_path, dataset_stats, chart_paths, test_evaluation)
    summary_path = output / "training_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "ruBERT training report built state=%s output=%s charts=%s",
        state_path,
        output,
        len(chart_paths),
    )
    return summary


def _find_latest_trainer_state(model_dir: Path) -> Path:
    candidates = list(model_dir.glob("checkpoint-*/trainer_state.json"))
    if not candidates:
        raise FileNotFoundError(f"No trainer_state.json found under {model_dir}")

    return max(candidates, key=lambda path: int(path.parent.name.removeprefix("checkpoint-")))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_dataset_stats(dataset_dir: Path) -> dict[str, Any]:
    label_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    split_counts: dict[str, int] = {}
    for split in ("train", "validation", "test"):
        path = dataset_dir / f"{split}.jsonl"
        rows = 0
        with path.open(encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                row = json.loads(line)
                label_counts.update(row.get("label_names", []))
                source_counts.update([str(row.get("source", "unknown"))])
                rows += 1
        split_counts[split] = rows

    return {
        "split_counts": split_counts,
        "label_counts": dict(sorted(label_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
    }


def _build_charts(
    history: list[dict[str, Any]],
    dataset_stats: dict[str, Any],
    chart_dir: Path,
    test_evaluation: dict[str, Any] | None,
) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    chart_paths = [
        _save_training_overview(history, dataset_stats, chart_dir, plt),
        _save_loss_chart(history, chart_dir, plt),
        _save_validation_metrics_chart(history, chart_dir, plt),
        _save_learning_rate_chart(history, chart_dir, plt),
        _save_count_chart(
            dataset_stats["label_counts"],
            "Label distribution",
            chart_dir / "label_distribution.png",
            plt,
        ),
        _save_count_chart(
            dataset_stats["source_counts"],
            "Dataset sources",
            chart_dir / "source_distribution.png",
            plt,
        ),
    ]
    if test_evaluation is not None:
        chart_paths.extend(
            [
                _save_per_label_metrics_chart(test_evaluation["per_label"], chart_dir, plt),
                _save_prediction_balance_chart(test_evaluation["per_label"], chart_dir, plt),
            ]
        )
    return [str(path) for path in chart_paths]


def _save_training_overview(
    history: list[dict[str, Any]],
    dataset_stats: dict[str, Any],
    chart_dir: Path,
    plt: Any,
) -> Path:
    evaluation = [item for item in history if "eval_micro_f1" in item]
    final = evaluation[-1] if evaluation else {}
    best = max(evaluation, key=lambda item: item["eval_macro_f1"], default={})
    figure, axes = plt.subplots(2, 2, figsize=(15, 9), gridspec_kw={"height_ratios": [1.0, 1.25]})
    figure.suptitle("ruBERT moderation training overview", fontsize=18, fontweight="bold")

    metric_lines = (
        ("Final micro F1", final.get("eval_micro_f1")),
        ("Final macro F1", final.get("eval_macro_f1")),
        ("Final exact match", final.get("eval_exact_match")),
        ("Best macro F1", best.get("eval_macro_f1")),
        ("Best epoch", best.get("epoch")),
    )
    axes[0, 0].axis("off")
    axes[0, 0].text(0.03, 0.92, "Validation summary", fontsize=15, fontweight="bold", va="top")
    for index, (label, value) in enumerate(metric_lines):
        formatted = f"{value:.4f}" if isinstance(value, float) else str(value or "n/a")
        axes[0, 0].text(0.05, 0.70 - index * 0.14, label, fontsize=11, color="#475569")
        axes[0, 0].text(0.95, 0.70 - index * 0.14, formatted, fontsize=14, fontweight="bold", ha="right")

    split_counts = dataset_stats["split_counts"]
    axes[0, 1].bar(split_counts.keys(), split_counts.values(), color=["#2563EB", "#0EA5E9", "#14B8A6"])
    axes[0, 1].set(title="Dataset split", ylabel="Examples")
    _annotate_vertical_bars(axes[0, 1], list(split_counts.values()))
    axes[0, 1].grid(axis="y", alpha=0.2)

    metric_series = (
        ("eval_micro_f1", "micro F1", "#2563EB"),
        ("eval_macro_f1", "macro F1", "#F97316"),
        ("eval_exact_match", "exact match", "#16A34A"),
    )
    for key, label, color in metric_series:
        values = [(item["epoch"], item[key]) for item in evaluation if key in item]
        if values:
            axes[1, 0].plot(*zip(*values), marker="o", linewidth=2.2, label=label, color=color)
    axes[1, 0].set(title="Validation quality", xlabel="Epoch", ylabel="Score", ylim=(0.75, 1.0))
    axes[1, 0].grid(alpha=0.25)
    axes[1, 0].legend(loc="lower right")

    label_counts = dataset_stats["label_counts"]
    labels = sorted(label_counts, key=label_counts.get, reverse=True)[:8]
    axes[1, 1].barh(labels[::-1], [label_counts[label] for label in labels[::-1]], color="#7C3AED")
    axes[1, 1].set(title="Most represented labels", xlabel="Examples")
    axes[1, 1].grid(axis="x", alpha=0.2)
    return _save_figure(figure, chart_dir / "training_overview.png")


def _save_loss_chart(history: list[dict[str, Any]], chart_dir: Path, plt: Any) -> Path:
    train = [(item["step"], item["loss"]) for item in history if "loss" in item and "step" in item]
    evaluation = [(item["step"], item["eval_loss"]) for item in history if "eval_loss" in item and "step" in item]
    figure, axis = plt.subplots(figsize=(13, 6))
    if train:
        axis.plot(*zip(*train), label="train loss", linewidth=1.0, color="#2563EB", alpha=0.8)
    if evaluation:
        axis.plot(*zip(*evaluation), label="validation loss", marker="o", linewidth=2.2, color="#F97316")
        best_step, best_loss = min(evaluation, key=lambda item: item[1])
        axis.annotate(
            f"best validation loss\n{best_loss:.4f}",
            xy=(best_step, best_loss),
            xytext=(10, 18),
            textcoords="offset points",
            arrowprops={"arrowstyle": "->", "color": "#F97316"},
        )
    axis.set(title="Training and validation loss", xlabel="Step", ylabel="Loss", yscale="log")
    axis.grid(alpha=0.25)
    axis.legend()
    return _save_figure(figure, chart_dir / "loss_by_step.png")


def _save_validation_metrics_chart(history: list[dict[str, Any]], chart_dir: Path, plt: Any) -> Path:
    evaluation = [item for item in history if "eval_micro_f1" in item]
    figure, axis = plt.subplots(figsize=(13, 6))
    for key, label, color in (
        ("eval_micro_f1", "micro F1", "#2563EB"),
        ("eval_macro_f1", "macro F1", "#F97316"),
        ("eval_exact_match", "exact match", "#16A34A"),
    ):
        values = [(item["epoch"], item[key]) for item in evaluation if key in item]
        if values:
            axis.plot(*zip(*values), marker="o", linewidth=2.2, label=label, color=color)
            epoch, value = values[-1]
            axis.annotate(f"{value:.4f}", xy=(epoch, value), xytext=(8, 0), textcoords="offset points", va="center")
    best = max(evaluation, key=lambda item: item["eval_macro_f1"], default=None)
    if best is not None:
        axis.axvline(best["epoch"], color="#F97316", linestyle="--", alpha=0.65)
        axis.text(best["epoch"], 0.755, f"best macro F1: epoch {best['epoch']:.0f}", ha="center", color="#9A3412")
    axis.set(title="Validation quality by epoch", xlabel="Epoch", ylabel="Score", ylim=(0.75, 1.0))
    axis.grid(alpha=0.25)
    axis.legend()
    return _save_figure(figure, chart_dir / "validation_metrics_by_epoch.png")


def _save_learning_rate_chart(history: list[dict[str, Any]], chart_dir: Path, plt: Any) -> Path:
    values = [(item["step"], item["learning_rate"]) for item in history if "learning_rate" in item and "step" in item]
    figure, axis = plt.subplots(figsize=(13, 5))
    if values:
        axis.plot(*zip(*values), linewidth=1.5, color="#0F766E")
    axis.set(title="Learning rate schedule", xlabel="Step", ylabel="Learning rate", yscale="log")
    axis.grid(alpha=0.25)
    return _save_figure(figure, chart_dir / "learning_rate_by_step.png")


def _save_count_chart(
    counts: dict[str, int],
    title: str,
    path: Path,
    plt: Any,
) -> Path:
    figure, axis = plt.subplots(figsize=(13, 7))
    labels = sorted(counts, key=counts.get)
    values = [counts[label] for label in labels]
    total = sum(values)
    bars = axis.barh(labels, values, color="#2563EB")
    for bar, value in zip(bars, values):
        axis.text(value, bar.get_y() + bar.get_height() / 2, f" {value:,} ({value / total:.1%})", va="center", fontsize=9)
    axis.set(title=title, xlabel="Examples")
    axis.grid(axis="x", alpha=0.25)
    return _save_figure(figure, path)


def _save_per_label_metrics_chart(per_label: dict[str, dict[str, float]], chart_dir: Path, plt: Any) -> Path:
    labels = sorted(
        (label for label in per_label if per_label[label]["target_count"] > 0),
        key=lambda label: per_label[label]["f1"],
    )
    unsupported = sorted(label for label in per_label if per_label[label]["target_count"] == 0)
    figure, axis = plt.subplots(figsize=(13, 8))
    positions = list(range(len(labels)))
    width = 0.24
    for offset, key, title, color in (
        (-width, "precision", "precision", "#2563EB"),
        (0.0, "recall", "recall", "#16A34A"),
        (width, "f1", "F1", "#F97316"),
    ):
        axis.bar([position + offset for position in positions], [per_label[label][key] for label in labels], width, label=title, color=color)
    axis.set(title="Test quality for each moderation label", xlabel="Label", ylabel="Score", ylim=(0.0, 1.0))
    axis.set_xticks(positions, labels, rotation=45)
    axis.grid(axis="y", alpha=0.25)
    axis.legend(ncols=3, loc="upper left")
    if unsupported:
        axis.text(
            0.99,
            0.02,
            f"No test examples: {', '.join(unsupported)}",
            transform=axis.transAxes,
            ha="right",
            va="bottom",
            fontsize=10,
            color="#64748B",
        )
    return _save_figure(figure, chart_dir / "test_per_label_metrics.png")


def _save_prediction_balance_chart(per_label: dict[str, dict[str, float]], chart_dir: Path, plt: Any) -> Path:
    labels = sorted(
        (label for label in per_label if per_label[label]["target_count"] > 0),
        key=lambda label: per_label[label]["target_count"],
    )
    figure, axis = plt.subplots(figsize=(13, 8))
    positions = list(range(len(labels)))
    width = 0.38
    target_counts = [per_label[label]["target_count"] for label in labels]
    predicted_counts = [per_label[label]["predicted_count"] for label in labels]
    axis.bar([position - width / 2 for position in positions], target_counts, width, label="target", color="#2563EB")
    axis.bar([position + width / 2 for position in positions], predicted_counts, width, label="predicted", color="#F97316")
    axis.set(title="Test label balance: target vs predicted", xlabel="Label", ylabel="Positive examples")
    axis.set_xticks(positions, labels, rotation=45)
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    return _save_figure(figure, chart_dir / "test_prediction_balance.png")


def _save_figure(figure: Any, path: Path) -> Path:
    figure.tight_layout()
    figure.savefig(path, dpi=180, bbox_inches="tight")
    figure.clf()
    return path


def _annotate_vertical_bars(axis: Any, values: list[int]) -> None:
    for bar, value in zip(axis.patches, values):
        axis.text(bar.get_x() + bar.get_width() / 2, value, f"{value:,}", ha="center", va="bottom", fontsize=10)


def _build_summary(
    state: dict[str, Any],
    state_path: Path,
    dataset_stats: dict[str, Any],
    chart_paths: list[str],
    test_evaluation: dict[str, Any] | None,
) -> dict[str, Any]:
    evaluation = [item for item in state.get("log_history", []) if "eval_micro_f1" in item]
    final_evaluation = evaluation[-1] if evaluation else {}
    return {
        "trainer_state_path": str(state_path),
        "best_checkpoint": state.get("best_model_checkpoint"),
        "best_metric": state.get("best_metric"),
        "completed_epoch": state.get("epoch"),
        "global_step": state.get("global_step"),
        "num_train_epochs": state.get("num_train_epochs"),
        "final_validation_metrics": {
            key.removeprefix("eval_"): value
            for key, value in final_evaluation.items()
            if key.startswith("eval_")
        },
        "evaluation_history": [
            {
                "epoch": item.get("epoch"),
                "step": item.get("step"),
                "loss": item.get("eval_loss"),
                "micro_f1": item.get("eval_micro_f1"),
                "macro_f1": item.get("eval_macro_f1"),
                "exact_match": item.get("eval_exact_match"),
            }
            for item in evaluation
        ],
        "dataset": dataset_stats,
        "test_evaluation": test_evaluation,
        "charts": chart_paths,
    }


def _evaluate_test_split(model_dir: Path, dataset_dir: Path) -> dict[str, Any]:
    import numpy as np
    from sklearn.metrics import f1_score, precision_recall_fscore_support

    from scripts.training.evaluate_rubert_moderation import _load_jsonl, _predict

    rows = _load_jsonl(dataset_dir / "test.jsonl")
    probabilities, targets, label_names = _predict(model_dir, rows, batch_size=64)
    threshold_data = _load_json(model_dir / "thresholds.json")
    thresholds = np.asarray([float(threshold_data.get(label, 0.5)) for label in label_names], dtype=np.float32)
    predictions = (probabilities >= thresholds).astype(np.int32)
    precision, recall, f1, _support = precision_recall_fscore_support(
        targets,
        predictions,
        average=None,
        zero_division=0,
    )
    per_label = {
        label: {
            "precision": round(float(precision[index]), 6),
            "recall": round(float(recall[index]), 6),
            "f1": round(float(f1[index]), 6),
            "target_count": int(targets[:, index].sum()),
            "predicted_count": int(predictions[:, index].sum()),
        }
        for index, label in enumerate(label_names)
    }
    return {
        "rows": len(rows),
        "micro_f1": round(float(f1_score(targets, predictions, average="micro", zero_division=0)), 6),
        "macro_f1": round(float(f1_score(targets, predictions, average="macro", zero_division=0)), 6),
        "per_label": per_label,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    summary = build_training_report(
        model_dir=args.model_dir,
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        include_test_evaluation=args.include_test_evaluation,
    )
    sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
