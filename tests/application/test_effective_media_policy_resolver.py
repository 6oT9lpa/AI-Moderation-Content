from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.application.effective_media_policy_resolver import EffectiveMediaPolicyResolver
from src.application.media_policy_conflict_error import MediaPolicyConflictError
from src.application.ports.media.media_policy_repository import MediaPolicyRepository
from src.domain.media.media_policy_snapshot import MediaPolicySnapshot
from src.domain.media.media_rule_policy import MediaRulePolicy
from src.infrastructure.media.yaml_media_policy_defaults_provider import YamlMediaPolicyDefaultsProvider


CONFIG_DIR = Path(__file__).parents[2] / "configs" / "policies"


class _Repository(MediaPolicyRepository):
    def __init__(self) -> None:
        self.snapshot: MediaPolicySnapshot | None = None
        self.audit: list[str] = []

    async def get_active(self, platform: str, guild_id: str) -> MediaPolicySnapshot | None:
        return self.snapshot

    async def save(self, *, platform: str, guild_id: str, policy: MediaRulePolicy, defaults_version: str,
                   expected_revision: int, updated_by: str) -> MediaPolicySnapshot | None:
        current = self.snapshot.revision if self.snapshot else 0
        if current != expected_revision:
            return None
        now = datetime.now(timezone.utc)
        self.snapshot = MediaPolicySnapshot(
            platform="discord", guild_id=guild_id, schema_version="media-policy-v1",
            defaults_version=defaults_version, revision=current + 1, policy=policy,
            created_at=self.snapshot.created_at if self.snapshot else now,
            updated_at=now, updated_by=updated_by,
        )
        self.audit.append("SAVE")
        return self.snapshot

    async def reset(self, *, platform: str, guild_id: str, expected_revision: int, updated_by: str) -> bool:
        if self.snapshot is None or self.snapshot.revision != expected_revision:
            return False
        self.snapshot = None
        self.audit.append("RESET")
        return True


@pytest.mark.asyncio
async def test_yaml_then_full_database_snapshot_then_reset() -> None:
    repository = _Repository()
    resolver = _resolver(repository)

    defaults = await resolver.resolve("discord", "123")
    assert defaults.source == "YAML_DEFAULT"
    assert defaults.revision == 0

    changed = defaults.media.model_copy(
        update={"ocr": defaults.media.ocr.model_copy(update={"version": "guild-ocr-v1"})}
    )
    saved = await resolver.save(
        platform="discord", guild_id="123", policy=changed, expected_revision=0, updated_by="456"
    )
    assert saved.source == "DATABASE"
    assert saved.revision == 1
    assert saved.media.ocr.version == "guild-ocr-v1"

    reset = await resolver.reset(
        platform="discord", guild_id="123", expected_revision=1, updated_by="456"
    )
    assert reset.source == "YAML_DEFAULT"
    assert repository.audit == ["SAVE", "RESET"]


@pytest.mark.asyncio
async def test_revision_conflict_does_not_overwrite_snapshot() -> None:
    repository = _Repository()
    resolver = _resolver(repository)
    defaults = await resolver.resolve("discord", "123")
    await resolver.save(
        platform="discord", guild_id="123", policy=defaults.media, expected_revision=0, updated_by="456"
    )

    with pytest.raises(MediaPolicyConflictError):
        await resolver.save(
            platform="discord", guild_id="123", policy=defaults.media, expected_revision=0, updated_by="789"
        )
    assert repository.snapshot is not None
    assert repository.snapshot.updated_by == "456"


def _resolver(repository: MediaPolicyRepository) -> EffectiveMediaPolicyResolver:
    defaults = YamlMediaPolicyDefaultsProvider(
        ocr_path=CONFIG_DIR / "ocr_rules.yaml", yolo_path=CONFIG_DIR / "yolo_rules.yaml"
    )
    return EffectiveMediaPolicyResolver(repository, defaults)
