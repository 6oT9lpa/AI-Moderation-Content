from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ShadowAcceptancePolicy:
    minimum_samples: int = 1_000
    minimum_precision: float = 0.90
    minimum_recall: float = 0.85
    maximum_action_disagreement_rate: float = 0.05
    maximum_severe_false_negatives: int = 0


def evaluate_shadow_report(
    report: dict[str, Any], policy: ShadowAcceptancePolicy
) -> list[str]:
    failures: list[str] = []
    checks = (
        (
            int(report.get("samples", 0)) >= policy.minimum_samples,
            "insufficient samples",
        ),
        (
            float(report.get("precision", 0.0)) >= policy.minimum_precision,
            "precision below threshold",
        ),
        (
            float(report.get("recall", 0.0)) >= policy.minimum_recall,
            "recall below threshold",
        ),
        (
            float(report.get("action_disagreement_rate", 1.0))
            <= policy.maximum_action_disagreement_rate,
            "action disagreement above threshold",
        ),
        (
            int(report.get("severe_false_negatives", -1))
            <= policy.maximum_severe_false_negatives,
            "severe false negatives above threshold",
        ),
    )
    failures.extend(message for passed, message in checks if not passed)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail unless a shadow moderation report meets rollout thresholds."
    )
    parser.add_argument("report", type=Path)
    parser.add_argument("--minimum-samples", type=int, default=1_000)
    parser.add_argument("--minimum-precision", type=float, default=0.90)
    parser.add_argument("--minimum-recall", type=float, default=0.85)
    parser.add_argument("--maximum-action-disagreement-rate", type=float, default=0.05)
    parser.add_argument("--maximum-severe-false-negatives", type=int, default=0)
    args = parser.parse_args()
    failures = evaluate_shadow_report(
        json.loads(args.report.read_text(encoding="utf-8")),
        ShadowAcceptancePolicy(
            minimum_samples=args.minimum_samples,
            minimum_precision=args.minimum_precision,
            minimum_recall=args.minimum_recall,
            maximum_action_disagreement_rate=args.maximum_action_disagreement_rate,
            maximum_severe_false_negatives=args.maximum_severe_false_negatives,
        ),
    )
    print(
        json.dumps({"accepted": not failures, "failures": failures}, ensure_ascii=False)
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
