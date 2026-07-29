from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.training.curation.dataset_split_assigner import DatasetSplitAssigner
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema


class ProfanityDatasetAdapter:
    def __init__(
        self,
        *,
        schema: ModerationDatasetSchema,
        split_assigner: DatasetSplitAssigner,
    ) -> None:
        self._schema = schema
        self._split_assigner = split_assigner

    def build(self, *, input_path: Path, output_dir: Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        counts: Counter[str] = Counter()
        handles = {
            split: (output_dir / f"{split}.jsonl").open("a", encoding="utf-8", newline="\n")
            for split in ("train", "validation")
        }

        try:
            with input_path.open("r", encoding="utf-8-sig") as source:
                for line_number, raw in enumerate(source, 1):
                    if not raw.strip():
                        continue
                    try:
                        row = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"Invalid JSON at {input_path}:{line_number}") from exc

                    normalized = self._schema.normalize_row(
                        row,
                        record_id=f"profanity_{line_number}",
                    )
                    split = self._split_assigner.assign(normalized["text"])
                    handles[split].write(
                        json.dumps(normalized, ensure_ascii=False, separators=(",", ":")) + "\n"
                    )
                    counts[f"written_{split}"] += 1
                    counts.update(f"label_{label}" for label in normalized["label_names"])
        finally:
            for handle in handles.values():
                handle.close()

        return {
            "source": str(input_path),
            "rows": sum(value for key, value in counts.items() if key.startswith("written_")),
            "counts": dict(counts),
        }
