from __future__ import annotations

import json

from scripts.training.build_rubert_training_report import (
    _build_summary,
    _collect_dataset_stats,
    _find_latest_trainer_state,
)


def test_training_report_uses_highest_checkpoint_and_counts_dataset_rows(tmp_path, structured_test_logger) -> None:
    model_dir = tmp_path / "model"
    dataset_dir = tmp_path / "dataset"
    for step in (100, 200):
        checkpoint = model_dir / f"checkpoint-{step}"
        checkpoint.mkdir(parents=True)
        (checkpoint / "trainer_state.json").write_text("{}", encoding="utf-8")
    dataset_dir.mkdir()
    for split, rows in {
        "train": [
            {"label_names": ["SAFE"], "source": "public_dataset"},
            {"label_names": ["TOXIC"], "source": "project"},
        ],
        "validation": [{"label_names": ["SAFE"], "source": "project"}],
        "test": [{"label_names": ["TOXIC"], "source": "public_dataset"}],
    }.items():
        (dataset_dir / f"{split}.jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )

    actual = {
        "checkpoint": _find_latest_trainer_state(model_dir).parent.name,
        "split_counts": _collect_dataset_stats(dataset_dir)["split_counts"],
        "label_counts": _collect_dataset_stats(dataset_dir)["label_counts"],
    }
    expected = {
        "checkpoint": "checkpoint-200",
        "split_counts": {"train": 2, "validation": 1, "test": 1},
        "label_counts": {"SAFE": 2, "TOXIC": 2},
    }

    structured_test_logger("training_report_data", {"expected": expected, "actual": actual})

    assert actual == expected


def test_training_report_summary_uses_final_evaluation_metrics(structured_test_logger) -> None:
    state = {
        "best_model_checkpoint": "checkpoint-100",
        "best_metric": 0.8,
        "epoch": 2.0,
        "global_step": 100,
        "num_train_epochs": 2,
        "log_history": [
            {"epoch": 1.0, "step": 50, "eval_micro_f1": 0.7, "eval_macro_f1": 0.6, "eval_loss": 0.3},
            {"epoch": 2.0, "step": 100, "eval_micro_f1": 0.8, "eval_macro_f1": 0.7, "eval_loss": 0.2},
        ],
    }
    summary = _build_summary(
        state,
        state_path=__file__,
        dataset_stats={"split_counts": {}, "label_counts": {}, "source_counts": {}},
        chart_paths=["chart.png"],
        test_evaluation=None,
    )
    expected = {"micro_f1": 0.8, "macro_f1": 0.7, "loss": 0.2}
    actual = summary["final_validation_metrics"]

    structured_test_logger("training_report_summary", {"expected": expected, "actual": actual})

    assert actual == expected
