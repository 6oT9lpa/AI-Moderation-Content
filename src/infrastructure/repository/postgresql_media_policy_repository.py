from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

from src.application.ports.media.media_policy_repository import MediaPolicyRepository
from src.domain.media.media_policy_snapshot import MediaPolicySnapshot
from src.domain.media.media_rule_policy import MediaRulePolicy
from src.infrastructure.database.connection import DatabaseConnection
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class PostgresqlMediaPolicyRepository(MediaPolicyRepository):
    def __init__(self, database: DatabaseConnection) -> None:
        self._database = database

    async def get_active(self, platform: str, guild_id: str) -> MediaPolicySnapshot | None:
        row = await self._database.fetch_one(
            """
            SELECT platform, guild_id, schema_version, defaults_version, revision,
                   policy_json, created_at, updated_at, updated_by
            FROM media_policy_snapshots
            WHERE platform = %s AND guild_id = %s AND policy_type = 'MEDIA' AND active = TRUE
            """,
            [platform, guild_id],
        )
        return self._snapshot(row) if row else None

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
        row = await self._database.fetch_one(
            """
            WITH saved AS (
                INSERT INTO media_policy_snapshots (
                    platform, guild_id, policy_type, schema_version, defaults_version,
                    revision, policy_json, active, updated_by
                )
                VALUES (%s, %s, 'MEDIA', 'media-policy-v1', %s, 1, %s, TRUE, %s)
                ON CONFLICT (platform, guild_id, policy_type) DO UPDATE SET
                    schema_version = EXCLUDED.schema_version,
                    defaults_version = EXCLUDED.defaults_version,
                    revision = media_policy_snapshots.revision + 1,
                    policy_json = EXCLUDED.policy_json,
                    active = TRUE,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_by = EXCLUDED.updated_by
                WHERE media_policy_snapshots.revision = %s
                   OR (media_policy_snapshots.active = FALSE AND %s = 0)
                RETURNING *
            ), audited AS (
                INSERT INTO media_policy_audit (
                    platform, guild_id, operation, revision, policy_json, updated_by
                )
                SELECT platform, guild_id, 'SAVE', revision, policy_json, updated_by FROM saved
            )
            SELECT platform, guild_id, schema_version, defaults_version, revision,
                   policy_json, created_at, updated_at, updated_by
            FROM saved
            """,
            [
                platform, guild_id, defaults_version, Jsonb(policy.model_dump(mode="json")),
                updated_by, expected_revision, expected_revision,
            ],
        )
        if row is None:
            logger.warning("Media policy save conflict platform=%s guild_id=%s expected_revision=%s", platform, guild_id, expected_revision)
            return None
        logger.info("Media policy saved platform=%s guild_id=%s revision=%s actor=%s", platform, guild_id, row["revision"], updated_by)
        return self._snapshot(row)

    async def reset(self, *, platform: str, guild_id: str, expected_revision: int, updated_by: str) -> bool:
        result = await self._database.execute(
            """
            WITH reset AS (
                UPDATE media_policy_snapshots
                SET active = FALSE, revision = revision + 1,
                    updated_at = CURRENT_TIMESTAMP, updated_by = %s
                WHERE platform = %s AND guild_id = %s AND policy_type = 'MEDIA'
                  AND active = TRUE AND revision = %s
                RETURNING platform, guild_id, revision, updated_by
            )
            INSERT INTO media_policy_audit (platform, guild_id, operation, revision, updated_by)
            SELECT platform, guild_id, 'RESET', revision, updated_by FROM reset
            """,
            [updated_by, platform, guild_id, expected_revision],
        )
        changed = result.rowcount == 1
        if changed:
            logger.info("Media policy reset platform=%s guild_id=%s actor=%s", platform, guild_id, updated_by)
        return changed

    @staticmethod
    def _snapshot(row: dict[str, Any]) -> MediaPolicySnapshot:
        return MediaPolicySnapshot(
            platform=row["platform"], guild_id=row["guild_id"], schema_version=row["schema_version"],
            defaults_version=row["defaults_version"], revision=int(row["revision"]),
            policy=MediaRulePolicy.model_validate(row["policy_json"]), created_at=_datetime(row["created_at"]),
            updated_at=_datetime(row["updated_at"]), updated_by=row["updated_by"],
        )


def _datetime(value: Any) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
