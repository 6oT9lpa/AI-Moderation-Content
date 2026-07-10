from datetime import datetime

from pydantic import Field

from src.contracts.api.api_model import ApiModel


class HealthResponseSchema(ApiModel):
    status: str = Field(pattern=r"^(ok|degraded)$")
    database_status: str = Field(pattern=r"^(ready|unavailable)$")
    rubert_status: str = Field(pattern=r"^(ready|unavailable|disabled)$")
    policy_status: str = Field(pattern=r"^(ready|unavailable)$")
    policy_version: str | None = Field(default=None, max_length=128)
    model_id: str | None = Field(default=None, max_length=128)
    timestamp: datetime
    correlation_id: str = Field(min_length=1, max_length=64)
