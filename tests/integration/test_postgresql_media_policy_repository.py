import os
from pathlib import Path

import pytest

from src.infrastructure.database.connection import DatabaseConnection
from src.infrastructure.media.yaml_media_policy_defaults_provider import YamlMediaPolicyDefaultsProvider
from src.infrastructure.repository.postgresql_media_policy_repository import PostgresqlMediaPolicyRepository


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_POSTGRESQL_URL"),
    reason="TEST_POSTGRESQL_URL is required for destructive disposable-database integration tests",
)
@pytest.mark.asyncio
async def test_snapshot_conflict_revision_reset_and_audit_against_postgresql() -> None:
    database = DatabaseConnection(os.environ["TEST_POSTGRESQL_URL"], reconnect_attempts=1)
    repository = PostgresqlMediaPolicyRepository(database)
    policy = YamlMediaPolicyDefaultsProvider(
        ocr_path=Path("configs/policies/ocr_rules.yaml"),
        yolo_path=Path("configs/policies/yolo_rules.yaml"),
    ).get_defaults()
    guild_id = "999999999999999991"
    try:
        first = await repository.save(
            platform="discord",
            guild_id=guild_id,
            policy=policy,
            defaults_version="integration-v1",
            expected_revision=0,
            updated_by="actor-1",
        )
        assert first is not None and first.revision == 1

        conflict = await repository.save(
            platform="discord",
            guild_id=guild_id,
            policy=policy,
            defaults_version="integration-v1",
            expected_revision=0,
            updated_by="actor-stale",
        )
        assert conflict is None

        second = await repository.save(
            platform="discord",
            guild_id=guild_id,
            policy=policy,
            defaults_version="integration-v1",
            expected_revision=1,
            updated_by="actor-2",
        )
        assert second is not None and second.revision == 2
        assert await repository.reset(
            platform="discord", guild_id=guild_id, expected_revision=2, updated_by="actor-3"
        )
        assert await repository.get_active("discord", guild_id) is None

        audit = await database.fetch_all(
            """
            SELECT operation, revision, updated_by
            FROM media_policy_audit
            WHERE platform = %s AND guild_id = %s
            ORDER BY id
            """,
            ["discord", guild_id],
        )
        assert [(row["operation"], row["revision"], row["updated_by"]) for row in audit] == [
            ("SAVE", 1, "actor-1"),
            ("SAVE", 2, "actor-2"),
            ("RESET", 3, "actor-3"),
        ]
    finally:
        await database.execute(
            "DELETE FROM media_policy_audit WHERE platform = %s AND guild_id = %s",
            ["discord", guild_id],
        )
        await database.execute(
            "DELETE FROM media_policy_snapshots WHERE platform = %s AND guild_id = %s",
            ["discord", guild_id],
        )
        await database.close()
