from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.domain.message_context import MessageContext
from src.domain.policy.policy_record import PolicyRecord
from src.domain.policy.policy_repository import PolicyRepository
from src.domain.policy.policy_resolution_result import PolicyResolutionResult
from src.domain.policy.policy_scope import PolicyScope
from src.domain.policy.policy_scope_type import PolicyScopeType
from src.domain.policy.policy_source import PolicySource
from src.domain.policy.policy_type import PolicyType
from src.infrastructure.logging.logger import get_logger
from src.modules.policy.policy_payload_validator import PolicyPayloadValidator
from src.modules.policy.yaml_policy_fallback_loader import YamlPolicyFallbackLoader

logger = get_logger(__name__)


class PolicyResolver:
    def __init__(
        self,
        repository: PolicyRepository | None,
        *,
        fallback_loader: YamlPolicyFallbackLoader | None = None,
        payload_validator: PolicyPayloadValidator | None = None,
    ) -> None:
        self._repository = repository
        self._fallback_loader = fallback_loader or YamlPolicyFallbackLoader()
        self._payload_validator = payload_validator or PolicyPayloadValidator()

    async def resolve(
        self,
        policy_type: PolicyType,
        context: MessageContext | dict[str, Any],
    ) -> PolicyResolutionResult:
        scope_chain = self.build_scope_chain(context)
        logger.info(
            "Resolving policy policy_type=%s scopes=%s",
            policy_type.value,
            [scope.model_dump(mode="json") for scope in scope_chain],
        )

        if self._repository is not None:
            try:
                db_policy = await self._resolve_from_db(policy_type, scope_chain)
            except Exception as exc:
                logger.warning(
                    "Policy DB unavailable, falling back to YAML policy_type=%s error=%s",
                    policy_type.value,
                    exc,
                    exc_info=True,
                )
            else:
                if db_policy is not None:
                    policy = self._payload_validator.validate(policy_type, db_policy.payload)
                    matched_scope = PolicyScope(
                        scope_type=db_policy.scope_type,
                        scope_id=db_policy.scope_id,
                        platform=db_policy.platform,
                    )
                    logger.info(
                        "Policy resolved from DB policy_type=%s policy_id=%s version=%s scope=%s",
                        policy_type.value,
                        db_policy.policy_id,
                        db_policy.version,
                        matched_scope.model_dump(mode="json"),
                    )
                    return PolicyResolutionResult(
                        policy=policy,
                        source=PolicySource.DB,
                        matched_scope=matched_scope,
                        fallback_used=False,
                        policy_id=db_policy.policy_id,
                        version=db_policy.version,
                    )

        fallback_policy = self._fallback_loader.load(policy_type)
        policy_id = str(getattr(fallback_policy, "policy_id", f"yaml_{policy_type.value.lower()}_policy"))
        version = str(getattr(fallback_policy, "version", "yaml"))

        logger.info(
            "Policy resolved from YAML policy_type=%s policy_id=%s version=%s",
            policy_type.value,
            policy_id,
            version,
        )
        return PolicyResolutionResult(
            policy=fallback_policy,
            source=PolicySource.YAML,
            matched_scope=None,
            fallback_used=True,
            policy_id=policy_id,
            version=version,
        )

    async def _resolve_from_db(
        self,
        policy_type: PolicyType,
        scope_chain: list[PolicyScope],
    ) -> PolicyRecord | None:
        if self._repository is None:
            return None

        policies = await self._repository.get_enabled_policies(policy_type, scope_chain)
        if not policies:
            return None

        return sorted(
            policies,
            key=lambda policy: (
                self._scope_rank(policy, scope_chain),
                -policy.priority,
                -policy.updated_at.timestamp(),
            ),
        )[0]

    def _scope_rank(self, policy: PolicyRecord, scope_chain: list[PolicyScope]) -> int:
        for index, scope in enumerate(scope_chain):
            if scope.matches(policy.scope_type, policy.scope_id, policy.platform):
                return index

        return len(scope_chain)

    def build_scope_chain(self, context: MessageContext | dict[str, Any]) -> list[PolicyScope]:
        metadata = self._extract_metadata(context)
        platform = self._extract_value(context, "platform")
        guild_id = self._extract_value(context, "guild_id")
        chat_id = self._extract_value(context, "chat_id") or metadata.get("chat_id")
        channel_id = self._extract_value(context, "channel_id")
        user_id = self._extract_value(context, "user_id")
        roles = self._extract_roles(metadata)

        scopes: list[PolicyScope] = []

        if user_id:
            scopes.append(PolicyScope(scope_type=PolicyScopeType.USER, scope_id=str(user_id), platform=platform))

        for role_id in roles:
            scopes.append(PolicyScope(scope_type=PolicyScopeType.ROLE, scope_id=str(role_id), platform=platform))

        if channel_id:
            scopes.append(PolicyScope(scope_type=PolicyScopeType.CHANNEL, scope_id=str(channel_id), platform=platform))

        if guild_id:
            scopes.append(PolicyScope(scope_type=PolicyScopeType.GUILD, scope_id=str(guild_id), platform=platform))
        elif chat_id:
            scopes.append(PolicyScope(scope_type=PolicyScopeType.CHAT, scope_id=str(chat_id), platform=platform))

        if platform:
            scopes.append(PolicyScope(scope_type=PolicyScopeType.PLATFORM, platform=str(platform)))

        scopes.append(PolicyScope(scope_type=PolicyScopeType.GLOBAL))
        return scopes

    def _extract_metadata(self, context: MessageContext | dict[str, Any]) -> dict[str, Any]:
        if isinstance(context, MessageContext):
            return dict(context.metadata)

        metadata = context.get("metadata", {})
        return dict(metadata) if isinstance(metadata, dict) else {}

    def _extract_value(self, context: MessageContext | dict[str, Any], name: str) -> str | None:
        if isinstance(context, MessageContext):
            value = getattr(context, name, None)
            return str(value) if value is not None else None

        value = context.get(name)
        return str(value) if value is not None else None

    def _extract_roles(self, metadata: dict[str, Any]) -> list[str]:
        raw_roles = metadata.get("role_ids", metadata.get("roles", []))

        if isinstance(raw_roles, str):
            return [raw_roles]

        if isinstance(raw_roles, Sequence):
            return [str(role) for role in raw_roles]

        return []
