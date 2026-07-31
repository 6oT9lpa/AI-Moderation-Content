from pydantic import BaseModel, ConfigDict, Field, JsonValue

from src.domain.media.media_analysis_stage import MediaAnalysisStage


class MediaAnalysisRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: int = Field(gt=0)
    attachment_id: str = Field(min_length=1, max_length=128)
    stage: MediaAnalysisStage
    model_name: str | None = Field(default=None, max_length=128)
    model_version: str | None = Field(default=None, max_length=128)
    input_version: str = Field(min_length=1, max_length=128)
    policy_version: str = Field(min_length=1, max_length=128)
    output: dict[str, JsonValue] = Field(default_factory=dict)
    labels: tuple[str, ...] = Field(default=(), max_length=16)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    risk_score: int | None = Field(default=None, ge=0, le=100)
    latency_ms: int | None = Field(default=None, ge=0)
    error_summary: str | None = Field(default=None, max_length=256)

