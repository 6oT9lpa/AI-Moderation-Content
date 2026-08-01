from scripts.evaluation.check_shadow_acceptance import (
    ShadowAcceptancePolicy,
    evaluate_shadow_report,
)


def test_shadow_gate_accepts_report_at_thresholds() -> None:
    report = {
        "samples": 1_000,
        "precision": 0.90,
        "recall": 0.85,
        "action_disagreement_rate": 0.05,
        "severe_false_negatives": 0,
    }
    assert evaluate_shadow_report(report, ShadowAcceptancePolicy()) == []


def test_shadow_gate_reports_every_failed_safety_threshold() -> None:
    failures = evaluate_shadow_report(
        {
            "samples": 12,
            "precision": 0.2,
            "recall": 0.3,
            "action_disagreement_rate": 0.8,
            "severe_false_negatives": 2,
        },
        ShadowAcceptancePolicy(),
    )
    assert len(failures) == 5
