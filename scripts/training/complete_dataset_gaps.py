from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.curation.dataset_split_assigner import DatasetSplitAssigner
from src.training.curation.deduplicating_dataset_merger import (
    DeduplicatingDatasetMerger,
)
from src.training.curation.discord_invite_dataset_adapter import (
    DiscordInviteDatasetAdapter,
)
from src.training.curation.family_threat_augmentation_builder import (
    FamilyThreatAugmentationBuilder,
)
from src.training.curation.invite_augmentation_builder import InviteAugmentationBuilder
from src.training.curation.moderation_dataset_auditor import ModerationDatasetAuditor
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema
from src.training.curation.russian_family_toxic_adapter import (
    RussianFamilyToxicAdapter,
)
from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher
from src.training.curation.sensitive_topic_relabeler import SensitiveTopicRelabeler


DEFAULT_DATASET_DIR = PROJECT_ROOT / "data" / "exports" / "moderation_dataset_v2"
DEFAULT_TRAINING_CONFIG = PROJECT_ROOT / "configs" / "training" / "rubert_tiny2.yaml"
DEFAULT_CURATION_CONFIG = (
    PROJECT_ROOT / "configs" / "training" / "sensitive_topic_curation.yaml"
)
DEFAULT_REPORT_ROOT = PROJECT_ROOT / "data" / "reports"


def complete_gaps(args: argparse.Namespace) -> dict[str, Any]:
    dataset_dir = args.dataset_dir.resolve()
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=False)
    _require_file(dataset_dir / "train.jsonl")
    _require_file(dataset_dir / "validation.jsonl")

    schema = ModerationDatasetSchema.from_training_config(args.training_config)
    matcher = SensitiveTopicMatcher.from_yaml(args.curation_config)
    auditor = ModerationDatasetAuditor(schema=schema, matcher=matcher)
    baseline_audit = auditor.audit(
        dataset_dir=dataset_dir,
        report_path=report_dir / "baseline_audit.json",
    )

    with tempfile.TemporaryDirectory(
        prefix=".gap-completion-",
        dir=dataset_dir.parent,
    ) as temporary_name:
        temporary_dir = Path(temporary_name)
        invite_source_dir = temporary_dir / "discord_invite_source"
        invite_augmentation_dir = temporary_dir / "invite_augmentation"
        family_source_dir = temporary_dir / "russian_family_source"
        family_augmentation_dir = temporary_dir / "family_threat_augmentation"
        relabelled_dir = temporary_dir / "relabelled"
        relabelled_dir.mkdir(parents=True, exist_ok=True)

        relabeler = SensitiveTopicRelabeler(schema=schema, matcher=matcher)
        relabel_reports = {
            split: relabeler.relabel_file(
                input_path=dataset_dir / f"{split}.jsonl",
                output_path=relabelled_dir / f"{split}.jsonl",
                changes_path=report_dir / f"{split}_changes.jsonl",
                review_path=report_dir / f"{split}_review.jsonl",
            )
            for split in ("train", "validation")
        }

        invite_source_report = DiscordInviteDatasetAdapter(
            schema=schema,
            split_assigner=DatasetSplitAssigner(
                validation_fraction=args.invite_validation_fraction,
                seed=f"{args.seed}:discord-source",
            ),
        ).build(output_dir=invite_source_dir)
        invite_augmentation_report = InviteAugmentationBuilder(
            schema=schema,
            split_assigner=DatasetSplitAssigner(
                validation_fraction=args.invite_validation_fraction,
                seed=f"{args.seed}:invite-augmentation",
            ),
            target_rows=args.generated_invite_rows,
        ).build(output_dir=invite_augmentation_dir)
        family_source_report = RussianFamilyToxicAdapter(
            schema=schema,
            matcher=matcher,
            split_assigner=DatasetSplitAssigner(
                validation_fraction=args.family_validation_fraction,
                seed=f"{args.seed}:family-source",
            ),
        ).build(output_dir=family_source_dir)
        family_augmentation_report = FamilyThreatAugmentationBuilder(
            schema=schema,
            matcher=matcher,
            split_assigner=DatasetSplitAssigner(
                validation_fraction=args.family_validation_fraction,
                seed=f"{args.seed}:family-threat-augmentation",
            ),
        ).build(output_dir=family_augmentation_dir)

        merge_report = DeduplicatingDatasetMerger(schema=schema).merge_into(
            sources=(
                (
                    "moderation_dataset_v2_relabelled",
                    relabelled_dir / "train.jsonl",
                    relabelled_dir / "validation.jsonl",
                ),
                (
                    "discord_invite_source",
                    invite_source_dir / "train.jsonl",
                    invite_source_dir / "validation.jsonl",
                ),
                (
                    "controlled_invite_augmentation",
                    invite_augmentation_dir / "train.jsonl",
                    invite_augmentation_dir / "validation.jsonl",
                ),
                (
                    "russian_family_source",
                    family_source_dir / "train.jsonl",
                    family_source_dir / "validation.jsonl",
                ),
                (
                    "family_threat_augmentation",
                    family_augmentation_dir / "train.jsonl",
                    family_augmentation_dir / "validation.jsonl",
                ),
            ),
            target_dir=dataset_dir,
        )

    final_audit = auditor.audit(
        dataset_dir=dataset_dir,
        report_path=report_dir / "final_audit.json",
    )
    _assert_audit_clean(final_audit)
    _assert_gap_targets(
        final_audit,
        minimum_invite_train=args.minimum_invite_train,
        minimum_invite_validation=args.minimum_invite_validation,
        minimum_family_threat_validation=args.minimum_family_threat_validation,
    )

    result = {
        "dataset_dir": str(dataset_dir),
        "report_dir": str(report_dir),
        "semantic_contract": {
            "family_only_hate_generated": 0,
            "family_insult_labels": ["TOXIC"],
            "family_threat_labels": ["THREAT", "TOXIC"],
            "hate_rule": "HATE is reserved for attacks against protected groups",
        },
        "baseline_audit": baseline_audit,
        "relabel": relabel_reports,
        "sources": {
            "discord_invite": invite_source_report,
            "invite_augmentation": invite_augmentation_report,
            "russian_family": family_source_report,
            "family_threat_augmentation": family_augmentation_report,
        },
        "merge": merge_report,
        "final_audit": final_audit,
    }
    (report_dir / "run_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    parser = argparse.ArgumentParser(
        description="Complete INVITE and correctly-labelled family moderation gaps."
    )
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--training-config", type=Path, default=DEFAULT_TRAINING_CONFIG)
    parser.add_argument("--curation-config", type=Path, default=DEFAULT_CURATION_CONFIG)
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_ROOT / f"dataset_gap_completion_{timestamp}",
    )
    parser.add_argument("--seed", default="dataset-gap-completion-v1")
    parser.add_argument("--generated-invite-rows", type=int, default=2_200)
    parser.add_argument("--invite-validation-fraction", type=float, default=0.12)
    parser.add_argument("--family-validation-fraction", type=float, default=0.15)
    parser.add_argument("--minimum-invite-train", type=int, default=2_000)
    parser.add_argument("--minimum-invite-validation", type=int, default=200)
    parser.add_argument(
        "--minimum-family-threat-validation",
        type=int,
        default=200,
    )
    return parser


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required file does not exist: {path}")


def _assert_audit_clean(report: dict[str, Any]) -> None:
    if report["cross_split_normalized_overlap"]:
        raise ValueError("Final dataset contains cross-split text overlap")
    for split, split_report in report["splits"].items():
        if split_report["duplicate_normalized_texts"]:
            raise ValueError(f"Final {split} contains normalized text duplicates")
        if split_report["duplicate_ids"]:
            raise ValueError(f"Final {split} contains duplicate ids")
        if split_report["high_confidence_rule_misses"]:
            raise ValueError(
                f"Final {split} still contains high-confidence relabeling misses"
            )
        if any(split_report["structural_issues"].values()):
            raise ValueError(f"Final {split} contains structural inconsistencies")


def _assert_gap_targets(
    report: dict[str, Any],
    *,
    minimum_invite_train: int,
    minimum_invite_validation: int,
    minimum_family_threat_validation: int,
) -> None:
    train = report["splits"]["train"]
    validation = report["splits"]["validation"]
    invite_train = train["label_counts"].get("INVITE", 0)
    invite_validation = validation["label_counts"].get("INVITE", 0)
    family_threat_validation = (
        validation["topic_label_counts"].get("family", {}).get("THREAT", 0)
    )

    if invite_train < minimum_invite_train:
        raise ValueError(
            f"INVITE train count {invite_train} is below {minimum_invite_train}"
        )
    if invite_validation < minimum_invite_validation:
        raise ValueError(
            "INVITE validation count "
            f"{invite_validation} is below {minimum_invite_validation}"
        )
    if family_threat_validation < minimum_family_threat_validation:
        raise ValueError(
            "Family THREAT validation count "
            f"{family_threat_validation} is below {minimum_family_threat_validation}"
        )


def main() -> None:
    args = build_parser().parse_args()
    result = complete_gaps(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
