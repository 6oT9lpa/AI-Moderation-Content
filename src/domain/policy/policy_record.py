from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.policy.policy_scope_type import PolicyScopeType
from src.domain.policy.policy_type import PolicyType


class PolicyRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str
    policy_type: PolicyType
    scope_type: PolicyScopeType
    scope_id: str | None = None
    platform: str | None = None
    version: str
    payload: dict[str, Any]
    enabled: bool = True
    priority: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_scope(self) -> "PolicyRecord":
        if self.scope_type == PolicyScopeType.GLOBAL:
            return self

        if self.scope_type == PolicyScopeType.PLATFORM and not self.platform:
            raise ValueError("Platform policy scope requires platform")

        if self.scope_type != PolicyScopeType.PLATFORM and not self.scope_id:
            raise ValueError(f"{self.scope_type.value} policy scope requires scope_id")

        return self
