from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.policy.policy_record import PolicyRecord
from src.domain.policy.policy_scope import PolicyScope
from src.domain.policy.policy_type import PolicyType


class PolicyRepository(ABC):
    @abstractmethod
    async def get_enabled_policies(
        self,
        policy_type: PolicyType,
        scopes: list[PolicyScope],
    ) -> list[PolicyRecord]:
        raise NotImplementedError

    @abstractmethod
    async def get_policy_by_id(self, policy_id: str) -> PolicyRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def save_policy(self, policy_record: PolicyRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    async def disable_policy(self, policy_id: str) -> None:
        raise NotImplementedError
