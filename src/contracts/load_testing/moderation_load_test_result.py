from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModerationLoadTestResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total_messages: int = Field(ge=0)
    succeeded_messages: int = Field(ge=0)
    failed_messages: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    elapsed_seconds: float = Field(ge=0.0)
    achieved_messages_per_second: float = Field(ge=0.0)
    latency_mean_ms: float = Field(ge=0.0)
    latency_p50_ms: float = Field(ge=0.0)
    latency_p95_ms: float = Field(ge=0.0)
    latency_p99_ms: float = Field(ge=0.0)
    status_counts: dict[str, int]
    error_counts: dict[str, int]
    targets_met: bool
