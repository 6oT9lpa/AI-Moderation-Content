from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModerationLoadTestConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    base_url: str = "http://127.0.0.1:8000"
    channel_count: int = Field(default=20, ge=1, le=1_000)
    user_count: int = Field(default=100, ge=1, le=10_000)
    messages_per_user: int = Field(default=5, ge=1, le=100)
    duration_seconds: float = Field(default=60.0, gt=0, le=3_600)
    max_in_flight: int = Field(default=20, ge=1, le=500)
    request_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    min_success_rate: float = Field(default=0.99, ge=0.0, le=1.0)
    max_p95_latency_ms: float = Field(default=5_000.0, gt=0)

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        normalized = value.rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        return normalized

    @property
    def total_messages(self) -> int:
        return self.user_count * self.messages_per_user

    @property
    def target_messages_per_second(self) -> float:
        return self.total_messages / self.duration_seconds
