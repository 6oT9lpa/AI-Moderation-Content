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

from src.training.curation.civil_comments_adapter import CivilCommentsAdapter
from src.training.curation.dataset_split_assigner import DatasetSplitAssigner
from src.training.curation.deduplicating_dataset_merger import DeduplicatingDatasetMerger
from src.training.curation.measuring_hate_speech_adapter import MeasuringHateSpeechAdapter
from src.training.curation.moderation_dataset_auditor import ModerationDatasetAuditor
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema
from src.training.curation.profanity_dataset_adapter import ProfanityDatasetAdapter
from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher
from src.training.curation.sensitive_topic_relabeler import SensitiveTopicRelabeler


DEFAULT_DATASET_DIR = PROJECT_ROOT / "data" / "exports" / "moderation_dataset_v2"
DEFAULT_PROFANITY_PATH = (
    Path.home() / "Downloads" / "123" / "profanity" / "data" / "profanity_train.jsonl"
)
DEFAULT_TRAINING_CONFIG = PROJECT_ROOT / "configs" / "training" / "rubert_tiny2.yaml"
DEFAULT_CURATION_CONFIG = PROJECT_ROOT / "configs" / "training" / "sensitive_topic_curation.yaml"
DEFAULT_REPORT_ROOT = PROJECT_ROOT / "data" / "reports"


def curate(args: argparse.Namespace) -> dict[str, Any]:
    dataset_dir = args.dataset_dir.resolve()
    profanity_path = args.profanity_path.resolve()
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=False)

    _require_file(dataset_dir / "train.jsonl")
    _require_file(dataset_dir / "validation.jsonl")
    _require_file(profanity_path)

    schema = ModerationDatasetSchema.from_training_config(args.training_config)
    matcher = SensitiveTopicMatcher.from_yaml(args.curation_config)
    split_assigner = DatasetSplitAssigner(
        validation_fraction=args.validation_fraction,
        seed=args.seed,
    )
    relabeler = SensitiveTopicRelabeler(schema=schema, matcher=matcher)

    with tempfile.TemporaryDirectory(
        prefix=".sensitive-topic-curation-",
        dir=dataset_dir.parent,
    ) as temporary:
        temporary_dir = Path(temporary)
        relabelled_dir = temporary_dir / "relabelled"
        external_dir = temporary_dir / "external"

        relabel_reports = {}
        for split in ("train", "validation"):
            print(f"Relabeling {split}...", flush=True)
            relabel_reports[split] = relabeler.relabel_file(
                input_path=dataset_dir / f"{split}.jsonl",
                output_path=relabelled_dir / f"{split}.jsonl",
                changes_path=report_dir / f"{split}_changes.jsonl",
                review_path=report_dir / f"{split}_review.jsonl",
            )

        print("Building Measuring Hate Speech examples...", flush=True)
        measuring_report = MeasuringHateSpeechAdapter(
            schema=schema,
            split_assigner=split_assigner,
        ).build(output_dir=external_dir)

        print("Building Civil Comments sensitive-topic examples...", flush=True)
        civil_report = CivilCommentsAdapter(
            schema=schema,
            matcher=matcher,
            split_assigner=split_assigner,
        ).build(output_dir=external_dir)

        print("Adapting local profanity dataset...", flush=True)
        profanity_report = ProfanityDatasetAdapter(
            schema=schema,
            split_assigner=split_assigner,
        ).build(input_path=profanity_path, output_dir=external_dir)

        external_relabelled_dir = temporary_dir / "external_relabelled"
        external_relabel_reports = {}
        for split in ("train", "validation"):
            print(f"Applying topic rules to external {split}...", flush=True)
            external_relabel_reports[split] = relabeler.relabel_file(
                input_path=external_dir / f"{split}.jsonl",
                output_path=external_relabelled_dir / f"{split}.jsonl",
                changes_path=report_dir / f"external_{split}_changes.jsonl",
                review_path=report_dir / f"external_{split}_review.jsonl",
            )

        print("Merging and validating datasets...", flush=True)
        merge_report = DeduplicatingDatasetMerger(schema=schema).merge_into(
            sources=(
                (
                    "moderation_dataset_v2_relabelled",
                    relabelled_dir / "train.jsonl",
                    relabelled_dir / "validation.jsonl",
                ),
                (
                    "sensitive_external_and_profanity_v1",
                    external_relabelled_dir / "train.jsonl",
                    external_relabelled_dir / "validation.jsonl",
                ),
            ),
            target_dir=dataset_dir,
        )

    print("Auditing final dataset...", flush=True)
    audit_report = ModerationDatasetAuditor(schema=schema, matcher=matcher).audit(
        dataset_dir=dataset_dir,
        report_path=report_dir / "final_audit.json",
    )
    _assert_audit_clean(audit_report)
    result = {
        "dataset_dir": str(dataset_dir),
        "report_dir": str(report_dir),
        "configuration": {
            "training": str(args.training_config),
            "curation": str(args.curation_config),
            "validation_fraction": args.validation_fraction,
            "seed": args.seed,
        },
        "relabel": relabel_reports,
        "external_sources": {
            "measuring_hate_speech": measuring_report,
            "civil_comments": civil_report,
            "profanity": profanity_report,
        },
        "external_relabel": external_relabel_reports,
        "merge": merge_report,
        "audit": audit_report,
    }
    (report_dir / "run_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def audit_only(args: argparse.Namespace) -> dict[str, Any]:
    schema = ModerationDatasetSchema.from_training_config(args.training_config)
    matcher = SensitiveTopicMatcher.from_yaml(args.curation_config)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    return ModerationDatasetAuditor(schema=schema, matcher=matcher).audit(
        dataset_dir=args.dataset_dir,
        report_path=args.report_dir / "final_audit.json",
    )


def build_parser() -> argparse.ArgumentParser:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    parser = argparse.ArgumentParser(
        description="Relabel sensitive topics and merge licensed external moderation data."
    )
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--profanity-path", type=Path, default=DEFAULT_PROFANITY_PATH)
    parser.add_argument("--training-config", type=Path, default=DEFAULT_TRAINING_CONFIG)
    parser.add_argument("--curation-config", type=Path, default=DEFAULT_CURATION_CONFIG)
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_ROOT / f"sensitive_topic_curation_{timestamp}",
    )
    parser.add_argument("--validation-fraction", type=float, default=0.1)
    parser.add_argument("--seed", default="sensitive-topics-v1")
    parser.add_argument("--audit-only", action="store_true")
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
            raise ValueError(f"Final {split} still contains high-confidence relabeling misses")
        if any(split_report["structural_issues"].values()):
            raise ValueError(f"Final {split} contains structural inconsistencies")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = audit_only(args) if args.audit_only else curate(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
