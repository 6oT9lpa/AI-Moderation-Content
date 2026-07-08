from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from src.domain.policy.policy_scope import PolicyScope
from src.domain.policy.policy_source import PolicySource


class PolicyResolutionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    policy: Any
    source: PolicySource
    matched_scope: PolicyScope | None = None
    fallback_used: bool
    policy_id: str
    version: str
