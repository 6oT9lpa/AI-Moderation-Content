import json
import sys
from pathlib import Path
from types import SimpleNamespace

from src.training.curation.dataset_split_assigner import DatasetSplitAssigner
from src.training.curation.discord_invite_dataset_adapter import (
    DiscordInviteDatasetAdapter,
)
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema


CONFIG_PATH = Path("configs/training/rubert_tiny2.yaml")


class _FakeDataset(list):
    def select_columns(self, _columns):
        return self


def test_adapter_keeps_only_invite_rows(monkeypatch, tmp_path: Path) -> None:
    dataset = _FakeDataset(
        [
            {"label": 0, "msg_content": "Join us <DISCORD_INVITE>"},
            {"label": 1, "msg_content": "Fake verification <DISCORD_INVITE>"},
            {"label": 1, "msg_content": "ordinary scam <URL>"},
        ]
    )
    monkeypatch.setitem(
        sys.modules,
        "datasets",
        SimpleNamespace(load_dataset=lambda *_args, **_kwargs: dataset),
    )
    adapter = DiscordInviteDatasetAdapter(
        schema=ModerationDatasetSchema.from_training_config(CONFIG_PATH),
        split_assigner=DatasetSplitAssigner(
            validation_fraction=0.01,
            seed="test",
        ),
    )

    report = adapter.build(output_dir=tmp_path)

    rows = []
    for split in ("train", "validation"):
        rows.extend(
            json.loads(line)
            for line in (tmp_path / f"{split}.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    assert sum(
        report["counts"].get(f"written_{split}", 0)
        for split in ("train", "validation")
    ) == 2
    assert report["counts"]["skipped_without_invite"] == 1
    assert rows[0]["text"] == "Join us <INVITE>"
    assert rows[0]["label_names"] == ["INVITE", "URL"]
    assert rows[0]["severity"] == 1
    assert rows[1]["text"] == "Fake verification <INVITE>"
    assert rows[1]["label_names"] == ["INVITE", "SCAM", "URL"]
    assert rows[1]["severity"] == 4
