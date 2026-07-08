from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

from src.domain.policy.policy_record import PolicyRecord
from src.domain.policy.policy_repository import PolicyRepository
from src.domain.policy.policy_scope import PolicyScope
from src.domain.policy.policy_scope_type import PolicyScopeType
from src.domain.policy.policy_type import PolicyType
from src.infrastructure.database.connection import DatabaseConnection
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class PostgresqlPolicyRepository(PolicyRepository):
    def __init__(self, database: DatabaseConnection) -> None:
        self._database = database

    async def get_enabled_policies(
        self,
        policy_type: PolicyType,
        scopes: list[PolicyScope],
    ) -> list[PolicyRecord]:
        if not scopes:
            return []

        where_clauses: list[str] = []
        params: list[Any] = [policy_type.value]

        for scope in scopes:
            if scope.scope_type == PolicyScopeType.GLOBAL:
                where_clauses.append("(scope_type = %s)")
                params.append(scope.scope_type.value)
                continue

            if scope.scope_type == PolicyScopeType.PLATFORM:
                where_clauses.append("(scope_type = %s AND platform = %s)")
                params.extend([scope.scope_type.value, scope.platform])
                continue

            where_clauses.append(
                "(scope_type = %s AND scope_id = %s AND (platform IS NULL OR platform = %s))"
            )
            params.extend([scope.scope_type.value, scope.scope_id, scope.platform])

        query = f"""
            SELECT
                policy_id,
                policy_type,
                scope_type,
                scope_id,
                platform,
                version,
                payload_json,
                enabled,
                priority,
                created_at,
                updated_at
            FROM policy_records
            WHERE policy_type = %s
              AND enabled = TRUE
              AND ({' OR '.join(where_clauses)})
        """

        rows = await self._database.fetch_all(query, params)
        policies = [self._row_to_policy_record(row) for row in rows]
        logger.info(
            "Enabled policies loaded policy_type=%s count=%s",
            policy_type.value,
            len(policies),
        )
        return policies

    async def get_policy_by_id(self, policy_id: str) -> PolicyRecord | None:
        row = await self._database.fetch_one(
            """
            SELECT
                policy_id,
                policy_type,
                scope_type,
                scope_id,
                platform,
                version,
                payload_json,
                enabled,
                priority,
                created_at,
                updated_at
            FROM policy_records
            WHERE policy_id = %s
            """,
            [policy_id],
        )
        return self._row_to_policy_record(row) if row else None

    async def save_policy(self, policy_record: PolicyRecord) -> None:
        await self._database.execute(
            """
            INSERT INTO policy_records (
                policy_id,
                policy_type,
                scope_type,
                scope_id,
                platform,
                version,
                payload_json,
                enabled,
                priority,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (policy_id) DO UPDATE SET
                policy_type = EXCLUDED.policy_type,
                scope_type = EXCLUDED.scope_type,
                scope_id = EXCLUDED.scope_id,
                platform = EXCLUDED.platform,
                version = EXCLUDED.version,
                payload_json = EXCLUDED.payload_json,
                enabled = EXCLUDED.enabled,
                priority = EXCLUDED.priority,
                updated_at = EXCLUDED.updated_at
            """,
            [
                policy_record.policy_id,
                policy_record.policy_type.value,
                policy_record.scope_type.value,
                policy_record.scope_id,
                policy_record.platform,
                policy_record.version,
                Jsonb(policy_record.payload),
                policy_record.enabled,
                policy_record.priority,
                policy_record.created_at,
                policy_record.updated_at,
            ],
        )
        logger.info(
            "Policy record saved policy_id=%s policy_type=%s scope_type=%s scope_id=%s",
            policy_record.policy_id,
            policy_record.policy_type.value,
            policy_record.scope_type.value,
            policy_record.scope_id,
        )

    async def disable_policy(self, policy_id: str) -> None:
        await self._database.execute(
            """
            UPDATE policy_records
            SET enabled = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE policy_id = %s
            """,
            [policy_id],
        )
        logger.info("Policy record disabled policy_id=%s", policy_id)

    def _row_to_policy_record(self, row: dict[str, Any]) -> PolicyRecord:
        payload = row["payload_json"]
        if not isinstance(payload, dict):
            raise ValueError(f"Policy payload_json must be object policy_id={row['policy_id']}")

        return PolicyRecord(
            policy_id=row["policy_id"],
            policy_type=PolicyType(row["policy_type"]),
            scope_type=PolicyScopeType(row["scope_type"]),
            scope_id=row["scope_id"],
            platform=row["platform"],
            version=row["version"],
            payload=payload,
            enabled=bool(row["enabled"]),
            priority=int(row["priority"]),
            created_at=self._coerce_datetime(row["created_at"]),
            updated_at=self._coerce_datetime(row["updated_at"]),
        )

    def _coerce_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value

        return datetime.fromisoformat(str(value))
