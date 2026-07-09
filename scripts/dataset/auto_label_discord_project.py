from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.datasets.discord_auto_labeler import (
    DiscordAutoLabeler,
    DiscordAutoLabelerConfig,
    ToxicityScorer,
    load_jsonl,
    write_jsonl,
)

RAW_INPUT_PATH = Path("data/raw/discord_messages.jsonl")
OUTPUT_PATH = Path("data/exports/project_training_examples.jsonl")
MANIFEST_PATH = Path("data/exports/discord_auto_label_manifest.json")

TOXICITY_MODEL_NAME = "sismetanin/rubert-toxic-pikabu-2ch"
TOXICITY_THRESHOLD = 0.82
TOXICITY_CONTEXT_THRESHOLD = 0.92
TOXICITY_CURRENT_FLOOR_FOR_CONTEXT = 0.35
TOXICITY_BATCH_SIZE = 16
TOXICITY_CONTEXT_MESSAGES = 5


class HuggingFaceToxicityScorer(ToxicityScorer):
    def __init__(self) -> None:
        import torch
        from transformers import pipeline

        device = 0 if torch.cuda.is_available() else -1
        self._pipeline = pipeline(
            "text-classification",
            model=TOXICITY_MODEL_NAME,
            tokenizer=TOXICITY_MODEL_NAME,
            device=device,
        )

    def score(self, texts: list[str]) -> list[float]:
        if not texts:
            return []

        outputs = self._pipeline(
            texts,
            batch_size=TOXICITY_BATCH_SIZE,
            truncation=True,
            max_length=256,
        )
        return [self._to_toxic_score(output) for output in outputs]

    def _to_toxic_score(self, output: dict) -> float:
        label = str(output.get("label", "")).casefold()
        score = float(output.get("score", 0.0))
        if "toxic" in label or label in {"label_1", "1"}:
            return score
        return 1.0 - score


async def run(*, use_toxicity_model: bool = False) -> dict:
    rows = load_jsonl(RAW_INPUT_PATH)
    scorer = HuggingFaceToxicityScorer() if use_toxicity_model else None
    labeler = DiscordAutoLabeler(
        toxicity_scorer=scorer,
        config=DiscordAutoLabelerConfig(
            recent_messages_for_toxicity=TOXICITY_CONTEXT_MESSAGES,
            toxicity_threshold=TOXICITY_THRESHOLD,
            toxicity_context_threshold=TOXICITY_CONTEXT_THRESHOLD,
            toxicity_current_floor_for_context=TOXICITY_CURRENT_FLOOR_FOR_CONTEXT,
        ),
    )
    labeled_rows = await labeler.label_raw_rows(rows)
    write_jsonl(OUTPUT_PATH, labeled_rows)
    manifest = {
        "raw_rows": len(rows),
        "labeled_rows": len(labeled_rows),
        "output": str(OUTPUT_PATH),
        "toxicity_model_enabled": use_toxicity_model,
        "toxicity_labeling": "external_rubert" if use_toxicity_model else "local_rule_based",
        "toxicity_model_name": TOXICITY_MODEL_NAME if use_toxicity_model else None,
        "toxicity_threshold": TOXICITY_THRESHOLD,
        "toxicity_context_threshold": TOXICITY_CONTEXT_THRESHOLD,
        "toxicity_current_floor_for_context": TOXICITY_CURRENT_FLOOR_FOR_CONTEXT,
        "toxicity_context_messages": TOXICITY_CONTEXT_MESSAGES,
        "labels": Counter(row["primary_label"] for row in labeled_rows),
        "multi_labels": Counter(label for row in labeled_rows for label in row["labels"]),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    logging.getLogger().setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description="Auto-label exported Discord project messages.")
    parser.add_argument(
        "--use-toxicity-model",
        action="store_true",
        help="Use external ruBERT toxicity model for experiments. Default is local rule-based labeling.",
    )
    parser.add_argument(
        "--no-toxicity-model",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    import asyncio

    manifest = asyncio.run(run(use_toxicity_model=args.use_toxicity_model and not args.no_toxicity_model))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
