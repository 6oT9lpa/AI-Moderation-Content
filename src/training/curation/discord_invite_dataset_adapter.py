from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.dataset_split_assigner import DatasetSplitAssigner
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema


class DiscordInviteDatasetAdapter:
    REPO_ID = "wangyuancheng/discord-phishing-scam-clean"
    REVISION = "acd7149c2cd227c296f1f4f82411160dfcd9adb7"
    LICENSE = "MIT"
    _INVITE_MARKER_RE = re.compile(r"<DISCORD_INVITE>", re.IGNORECASE)

    def __init__(
        self,
        *,
        schema: ModerationDatasetSchema,
        split_assigner: DatasetSplitAssigner,
    ) -> None:
        self._schema = schema
        self._split_assigner = split_assigner

    def build(self, *, output_dir: Path) -> dict[str, Any]:
        from datasets import load_dataset

        dataset = load_dataset(
            self.REPO_ID,
            split="train",
            revision=self.REVISION,
        ).select_columns(["label", "msg_content"])

        output_dir.mkdir(parents=True, exist_ok=True)
        counts: Counter[str] = Counter()
        handles = {
            split: (output_dir / f"{split}.jsonl").open(
                "w",
                encoding="utf-8",
                newline="\n",
            )
            for split in ("train", "validation")
        }

        try:
            for row_index, row in enumerate(dataset):
                raw_text = str(row["msg_content"]).strip()
                if not self._INVITE_MARKER_RE.search(raw_text):
                    counts["skipped_without_invite"] += 1
                    continue

                upstream_label = int(row["label"])
                text = self._INVITE_MARKER_RE.sub("<INVITE>", raw_text)
                split = self._split_assigner.assign(text)
                labels = [ModerationLabel.INVITE, ModerationLabel.URL]
                severity = 1
                if upstream_label == 1:
                    labels.append(ModerationLabel.SCAM)
                    severity = 4
                record = self._schema.build_row(
                    text=text,
                    labels=labels,
                    severity=severity,
                    record_id=f"discord_invite_{row_index}",
                )
                handles[split].write(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
                counts[f"written_{split}"] += 1
                counts[f"upstream_label_{upstream_label}"] += 1
        finally:
            for handle in handles.values():
                handle.close()

        return {
            "source": self.REPO_ID,
            "revision": self.REVISION,
            "license": self.LICENSE,
            "upstream_rows": len(dataset),
            "counts": dict(counts),
        }
