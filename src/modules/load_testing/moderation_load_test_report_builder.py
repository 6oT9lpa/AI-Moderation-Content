from __future__ import annotations

from collections import Counter
from typing import Any

from src.contracts.load_testing.moderation_load_test_config import ModerationLoadTestConfig
from src.contracts.load_testing.moderation_load_test_result import ModerationLoadTestResult


def build_result(
    config: ModerationLoadTestConfig,
    request_results: list[dict[str, Any]],
    *,
    elapsed_seconds: float,
) -> ModerationLoadTestResult:
    latencies = sorted(float(result["latency_ms"]) for result in request_results)
    status_counts = Counter(str(result["status_code"]) for result in request_results if result["status_code"] is not None)
    error_counts = Counter(str(result["error_kind"]) for result in request_results if result["error_kind"])
    succeeded = sum(200 <= int(result["status_code"]) < 300 for result in request_results if result["status_code"] is not None)
    total = len(request_results)
    success_rate = succeeded / total if total else 0.0
    p95 = _percentile(latencies, 0.95)
    return ModerationLoadTestResult(
        total_messages=total,
        succeeded_messages=succeeded,
        failed_messages=total - succeeded,
        success_rate=round(success_rate, 6),
        elapsed_seconds=round(elapsed_seconds, 3),
        achieved_messages_per_second=round(total / elapsed_seconds, 3) if elapsed_seconds else 0.0,
        latency_mean_ms=round(sum(latencies) / total, 3) if total else 0.0,
        latency_p50_ms=round(_percentile(latencies, 0.50), 3),
        latency_p95_ms=round(p95, 3),
        latency_p99_ms=round(_percentile(latencies, 0.99), 3),
        status_counts=dict(sorted(status_counts.items())),
        error_counts=dict(sorted(error_counts.items())),
        targets_met=success_rate >= config.min_success_rate and p95 <= config.max_p95_latency_ms,
    )


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    index = (len(values) - 1) * quantile
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)
