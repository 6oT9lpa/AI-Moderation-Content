from abc import ABC, abstractmethod

from src.domain.media.media_policy_snapshot import MediaPolicySnapshot
from src.domain.media.media_rule_policy import MediaRulePolicy


class MediaPolicyRepository(ABC):
    @abstractmethod
    async def get_active(self, platform: str, guild_id: str) -> MediaPolicySnapshot | None:
        raise NotImplementedError

    @abstractmethod
    async def save(
        self,
        *,
        platform: str,
        guild_id: str,
        policy: MediaRulePolicy,
        defaults_version: str,
        expected_revision: int,
        updated_by: str,
    ) -> MediaPolicySnapshot | None:
        raise NotImplementedError

    @abstractmethod
    async def reset(self, *, platform: str, guild_id: str, expected_revision: int, updated_by: str) -> bool:
        raise NotImplementedError
