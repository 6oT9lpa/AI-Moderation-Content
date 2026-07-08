from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from src.domain.policy.policy_record import PolicyRecord
from src.domain.policy.policy_repository import PolicyRepository
from src.domain.policy.policy_scope import PolicyScope
from src.domain.policy.policy_source import PolicySource
from src.domain.policy.policy_type import PolicyType
from src.modules.decision.decision_policy import DecisionPolicy
from src.modules.policy.policy_resolver import PolicyResolver


class InMemoryPolicyRepository(PolicyRepository):
    def __init__(self, records: list[PolicyRecord] | None = None, *, fail: bool = False) -> None:
        self._records = records or []
        self._fail = fail

    async def get_enabled_policies(
        self,
        policy_type: PolicyType,
        scopes: list[PolicyScope],
    ) -> list[PolicyRecord]:
        if self._fail:
            raise RuntimeError("database unavailable")

        return [
            record
            for record in self._records
            if record.policy_type == policy_type
            and record.enabled
            and any(scope.matches(record.scope_type, record.scope_id, record.platform) for scope in scopes)
        ]

    async def get_policy_by_id(self, policy_id: str) -> PolicyRecord | None:
        return next((record for record in self._records if record.policy_id == policy_id), None)

    async def save_policy(self, policy_record: PolicyRecord) -> None:
        self._records.append(policy_record)

    async def disable_policy(self, policy_id: str) -> None:
        self._records = [
            record.model_copy(update={"enabled": False}) if record.policy_id == policy_id else record
            for record in self._records
        ]


class StaticYamlFallbackLoader:
    def __init__(self, policy: DecisionPolicy) -> None:
        self._policy = policy

    def load(self, policy_type: PolicyType) -> DecisionPolicy:
        assert policy_type == PolicyType.DECISION
        return self._policy


async def test_global_policy_from_db_overrides_yaml(structured_test_logger):
    db_policy = _record("db_global", scope_type="GLOBAL")
    resolver = _resolver([db_policy])

    result = await resolver.resolve(PolicyType.DECISION, _context())

    structured_test_logger(
        "policy",
        {
            "expected_source": PolicySource.DB,
            "actual_source": result.source,
            "expected_policy_id": "db_global",
            "actual_policy_id": result.policy_id,
        },
    )
    assert result.source == PolicySource.DB
    assert result.policy_id == "db_global"
    assert result.policy.policy_id == "db_global"
    assert not result.fallback_used


async def test_channel_policy_overrides_guild_platform_global():
    records = [
        _record("db_global", scope_type="GLOBAL"),
        _record("db_platform", scope_type="PLATFORM", platform="discord"),
        _record("db_guild", scope_type="GUILD", scope_id="guild_1", platform="discord"),
        _record("db_channel", scope_type="CHANNEL", scope_id="channel_1", platform="discord"),
    ]
    resolver = _resolver(records)

    result = await resolver.resolve(PolicyType.DECISION, _context())

    assert result.policy_id == "db_channel"
    assert result.matched_scope is not None
    assert result.matched_scope.scope_id == "channel_1"


async def test_user_policy_overrides_role_and_channel():
    records = [
        _record("db_channel", scope_type="CHANNEL", scope_id="channel_1", platform="discord"),
        _record("db_role", scope_type="ROLE", scope_id="mod", platform="discord"),
        _record("db_user", scope_type="USER", scope_id="user_1", platform="discord"),
    ]
    resolver = _resolver(records)

    result = await resolver.resolve(PolicyType.DECISION, _context(metadata={"role_ids": ["mod"]}))

    assert result.policy_id == "db_user"


async def test_disabled_policy_is_ignored():
    records = [
        _record("db_user_disabled", scope_type="USER", scope_id="user_1", platform="discord", enabled=False),
        _record("db_channel", scope_type="CHANNEL", scope_id="channel_1", platform="discord"),
    ]
    resolver = _resolver(records)

    result = await resolver.resolve(PolicyType.DECISION, _context())

    assert result.policy_id == "db_channel"


async def test_invalid_db_payload_fails_explicitly():
    resolver = _resolver(
        [
            PolicyRecord(
                policy_id="invalid_decision",
                policy_type=PolicyType.DECISION,
                scope_type="GLOBAL",
                version="1.0",
                payload={"policy_id": "invalid_decision"},
            )
        ]
    )

    with pytest.raises(ValidationError):
        await resolver.resolve(PolicyType.DECISION, _context())


async def test_yaml_fallback_used_when_db_policy_is_missing():
    resolver = _resolver([])

    result = await resolver.resolve(PolicyType.DECISION, _context())

    assert result.source == PolicySource.YAML
    assert result.policy_id == "yaml_decision"
    assert result.fallback_used


async def test_yaml_fallback_used_when_db_unavailable(caplog):
    resolver = PolicyResolver(
        InMemoryPolicyRepository(fail=True),
        fallback_loader=StaticYamlFallbackLoader(_decision_payload("yaml_decision")),
    )

    result = await resolver.resolve(PolicyType.DECISION, _context())

    assert result.source == PolicySource.YAML
    assert "Policy DB unavailable" in caplog.text


def _resolver(records: list[PolicyRecord]) -> PolicyResolver:
    return PolicyResolver(
        InMemoryPolicyRepository(records),
        fallback_loader=StaticYamlFallbackLoader(_decision_payload("yaml_decision")),
    )


def _record(
    policy_id: str,
    *,
    scope_type: str,
    scope_id: str | None = None,
    platform: str | None = None,
    enabled: bool = True,
    priority: int = 0,
) -> PolicyRecord:
    return PolicyRecord(
        policy_id=policy_id,
        policy_type=PolicyType.DECISION,
        scope_type=scope_type,
        scope_id=scope_id,
        platform=platform,
        version="1.0",
        payload=_decision_payload(policy_id).model_dump(mode="json"),
        enabled=enabled,
        priority=priority,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _decision_payload(policy_id: str) -> DecisionPolicy:
    return DecisionPolicy.model_validate(
        {
            "policy_id": policy_id,
            "version": "1.0",
            "action_thresholds": {
                "IGNORE": 0,
                "LOG": 10,
                "REVIEW": 40,
                "WARN": 50,
                "DELETE": 70,
                "DELETE_WARN": 80,
                "TIMEOUT": 90,
                "BAN": 95,
            },
            "action_priority": ["BAN", "TIMEOUT", "DELETE_WARN", "DELETE", "WARN", "REVIEW", "LOG", "IGNORE"],
        }
    )


def _context(metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "platform": "discord",
        "guild_id": "guild_1",
        "channel_id": "channel_1",
        "user_id": "user_1",
        "metadata": metadata or {},
    }
