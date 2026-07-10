from __future__ import annotations

from src.contracts.load_testing.moderation_load_test_config import ModerationLoadTestConfig
from src.modules.load_testing.moderation_load_test_report_builder import build_result


def test_report_builder_calculates_latency_and_success_targets(structured_test_logger) -> None:
    config = ModerationLoadTestConfig(min_success_rate=0.75, max_p95_latency_ms=250.0)
    request_results = [
        {"status_code": 200, "error_kind": None, "latency_ms": 100.0},
        {"status_code": 200, "error_kind": None, "latency_ms": 200.0},
        {"status_code": 503, "error_kind": "http_error", "latency_ms": 300.0},
        {"status_code": 201, "error_kind": None, "latency_ms": 400.0},
    ]

    result = build_result(config, request_results, elapsed_seconds=2.0)
    expected = {
        "succeeded_messages": 3,
        "failed_messages": 1,
        "success_rate": 0.75,
        "latency_p95_ms": 385.0,
        "targets_met": False,
    }
    actual = {key: getattr(result, key) for key in expected}

    structured_test_logger("load_report", {"expected": expected, "actual": actual})

    assert actual == expected
    assert result.status_counts == {"200": 2, "201": 1, "503": 1}
    assert result.error_counts == {"http_error": 1}
