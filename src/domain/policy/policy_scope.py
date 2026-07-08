from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.domain.policy.policy_scope_type import PolicyScopeType


class PolicyScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scope_type: PolicyScopeType
    scope_id: str | None = None
    platform: str | None = None

    def matches(self, scope_type: PolicyScopeType, scope_id: str | None, platform: str | None) -> bool:
        if self.scope_type != scope_type:
            return False

        if self.scope_type == PolicyScopeType.GLOBAL:
            return True

        if self.scope_type == PolicyScopeType.PLATFORM:
            return self.platform == platform

        return self.scope_id == scope_id
