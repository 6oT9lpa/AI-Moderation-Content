from pydantic import Field

from src.contracts.api.api_model import ApiModel


class ModerationMessageResponseSchema(ApiModel):
    correlation_id: str = Field(min_length=1, max_length=64)
    message_id: str = Field(min_length=1, max_length=64)
    labels: tuple[str, ...] = Field(max_length=14)
    primary_label: str = Field(max_length=32)
    rule_matches: tuple[str, ...] = Field(max_length=32)
    rubert_labels: tuple[str, ...] = Field(max_length=14)
    rubert_scores: dict[str, float] = Field(default_factory=dict)
    rubert_thresholds: dict[str, float] = Field(default_factory=dict)
    rubert_top_labels: tuple[str, ...] = Field(default=(), max_length=5)
    risk_score: float = Field(ge=0, le=100)
    risk_breakdown: tuple[str, ...] = Field(max_length=32)
    decision_action: str = Field(max_length=32)
    severity: int = Field(ge=0, le=5)
    reason: str = Field(max_length=256)
    policy_id: str = Field(max_length=128)
    policy_version: str = Field(max_length=128)
    execution_status: str = Field(max_length=32)
    execution_plan: tuple[str, ...] = Field(max_length=8)
    dataset_event_id: int = Field(gt=0)
    latency_ms: int = Field(ge=0)
    warnings: tuple[str, ...] = Field(default=(), max_length=8)
