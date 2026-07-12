from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_export_relabeler import ModerationExportRelabeler
from src.training.datasets.quota_backfill_examples import build_quota_backfill_candidates
from src.training.datasets.training_text_sanitizer import TrainingTextSanitizer


CHECKPOINT = Path("data/exports/rubert_moderation_v2/candidates_filtered_v2.jsonl")


def main() -> None:
    sanitizer = TrainingTextSanitizer()
    relabeler = ModerationExportRelabeler()
    additions = [row for row in build_quota_backfill_candidates() if row.source_id.startswith("invite_") and int(row.source_id.rsplit("_", 1)[1]) >= 60_000]
    with CHECKPOINT.open("a", encoding="utf-8") as file:
        for candidate in additions:
            text = sanitizer.sanitize(candidate.text)
            relabeled = relabeler.relabel_row({"model_text": text, "labels": [ModerationLabel.INVITE.value], "primary_label": ModerationLabel.INVITE.value, "severity": 3})
            updated = candidate.model_copy(update={
                "text": text,
                "labels": [ModerationLabel(label) for label in relabeled["labels"]],
                "primary_label": ModerationLabel(str(relabeled["primary_label"])),
                "severity": int(relabeled["severity"]),
            })
            file.write(updated.model_dump_json() + "\n")
    print(f"appended_invites={len(additions)} checkpoint={CHECKPOINT}")


if __name__ == "__main__":
    main()
