from src.application.media_policy_conflict_error import MediaPolicyConflictError
from src.application.ports.media.media_policy_defaults_provider import MediaPolicyDefaultsProvider
from src.application.ports.media.media_policy_repository import MediaPolicyRepository
from src.domain.media.media_policy_snapshot import EffectiveMediaPolicy
from src.domain.media.media_rule_policy import MediaRulePolicy


class EffectiveMediaPolicyResolver:
    def __init__(self, repository: MediaPolicyRepository, defaults: MediaPolicyDefaultsProvider) -> None:
        self._repository = repository
        self._defaults = defaults
        self._cache: dict[tuple[str, str, int, str, str], EffectiveMediaPolicy] = {}

    async def resolve(self, platform: str, guild_id: str) -> EffectiveMediaPolicy:
        self._validate_scope(platform, guild_id)
        snapshot = await self._repository.get_active(platform, guild_id)
        if snapshot is not None:
            key = (platform, guild_id, snapshot.revision, snapshot.policy.ocr.version, snapshot.policy.yolo.version)
            cached = self._cache.get(key)
            if cached is not None:
                return cached
            effective = EffectiveMediaPolicy(
                platform="discord",
                guild_id=guild_id,
                media=snapshot.policy,
                source="DATABASE",
                schema_version=snapshot.schema_version,
                defaults_version=snapshot.defaults_version,
                revision=snapshot.revision,
                updated_at=snapshot.updated_at,
                updated_by=snapshot.updated_by,
            )
            self._cache[key] = effective
            return effective
        defaults = self._defaults.get_defaults()
        return EffectiveMediaPolicy(
            platform="discord",
            guild_id=guild_id,
            media=defaults,
            source="YAML_DEFAULT",
            defaults_version=self._defaults_version(defaults),
            revision=0,
        )

    async def save(
        self,
        *,
        platform: str,
        guild_id: str,
        policy: MediaRulePolicy,
        expected_revision: int,
        updated_by: str,
    ) -> EffectiveMediaPolicy:
        self._validate_scope(platform, guild_id)
        saved = await self._repository.save(
            platform=platform,
            guild_id=guild_id,
            policy=policy,
            defaults_version=self._defaults_version(self._defaults.get_defaults()),
            expected_revision=expected_revision,
            updated_by=updated_by,
        )
        if saved is None:
            raise MediaPolicyConflictError("media policy revision conflict")
        self.invalidate(platform, guild_id)
        return await self.resolve(platform, guild_id)

    async def reset(self, *, platform: str, guild_id: str, expected_revision: int, updated_by: str) -> EffectiveMediaPolicy:
        self._validate_scope(platform, guild_id)
        if not await self._repository.reset(
            platform=platform, guild_id=guild_id, expected_revision=expected_revision, updated_by=updated_by
        ):
            raise MediaPolicyConflictError("media policy revision conflict")
        self.invalidate(platform, guild_id)
        return await self.resolve(platform, guild_id)

    def invalidate(self, platform: str, guild_id: str) -> None:
        self._cache = {key: value for key, value in self._cache.items() if key[:2] != (platform, guild_id)}

    @staticmethod
    def _defaults_version(policy: MediaRulePolicy) -> str:
        return f"{policy.ocr.version}:{policy.yolo.version}"

    @staticmethod
    def _validate_scope(platform: str, guild_id: str) -> None:
        if platform != "discord" or not guild_id.isdigit() or len(guild_id) > 32:
            raise ValueError("invalid media policy scope")
