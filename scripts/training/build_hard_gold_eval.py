from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.datasets.hard_gold_eval_pack import build_hard_gold_eval_pack


def main() -> None:
    output_dir = Path("data/eval/rubert_hard_gold_v1")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_hard_gold_eval_pack()
    (output_dir / "hard_gold.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    manifest = {"rows": len(rows), "label_counts": Counter(row["primary_label"] for row in rows), "annotation_status": "policy_verified", "not_for_training": True}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
