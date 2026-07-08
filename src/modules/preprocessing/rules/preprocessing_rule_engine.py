from __future__ import annotations

from typing import Any

from src.domain.message_context import MessageContext
from src.infrastructure.logging import get_logger
from src.modules.preprocessing.rules.preprocessing_rule_policy import PreprocessingRulePolicy
from src.modules.preprocessing.rules.preprocessing_rule_result import PreprocessingRuleResult
from src.modules.preprocessing.rules.preprocessing_rule_settings import PreprocessingRuleSettings

logger = get_logger(__name__)


class PreprocessingRuleEngine:
    def __init__(self, settings: PreprocessingRuleSettings | None = None) -> None:
        self._settings = settings or PreprocessingRuleSettings()
        logger.info("Preprocessing rule engine initialized settings=%s", self._settings)

    def evaluate(self, context: MessageContext) -> tuple[PreprocessingRuleResult, ...]:
        features = context.features

        if features is None:
            logger.warning("Preprocessing rule evaluation skipped reason=missing_features")
            return ()

        results: list[PreprocessingRuleResult] = []
        results.extend(self._evaluate_flood(context))
        results.extend(self._evaluate_spam(context))
        results.extend(self._evaluate_invite(context))
        results.extend(self._evaluate_links(context))
        results.extend(self._evaluate_evasion(context))

        logger.info(
            "Preprocessing rule evaluation finished message_id=%s matches=%s labels=%s",
            context.message_id,
            len(results),
            sorted({label.value for result in results for label in result.labels}),
        )
        return tuple(results)

    def _evaluate_flood(self, context: MessageContext) -> list[PreprocessingRuleResult]:
        features = context.features
        assert features is not None

        matches: list[PreprocessingRuleResult] = []
        flood = self._settings.flood

        if self._is_threshold_reached(flood.messages_10s, features.recent_user_messages_10s):
            matches.append(
                self._build_result(
                    "preprocessing.flood.messages_10s",
                    flood.messages_10s,
                    {"recent_user_messages_10s": features.recent_user_messages_10s},
                ),
            )

        if self._is_threshold_reached(flood.messages_60s, features.recent_user_messages_60s):
            matches.append(
                self._build_result(
                    "preprocessing.flood.messages_60s",
                    flood.messages_60s,
                    {"recent_user_messages_60s": features.recent_user_messages_60s},
                ),
            )

        if self._is_threshold_reached(flood.repeated_messages_10m, features.repeated_messages_10m):
            matches.append(
                self._build_result(
                    "preprocessing.flood.repeated_messages_10m",
                    flood.repeated_messages_10m,
                    {"repeated_messages_10m": features.repeated_messages_10m},
                ),
            )

        return matches

    def _evaluate_spam(self, context: MessageContext) -> list[PreprocessingRuleResult]:
        features = context.features
        assert features is not None

        matches: list[PreprocessingRuleResult] = []
        spam = self._settings.spam

        if self._is_threshold_reached(spam.mass_mentions, features.mention_count):
            matches.append(
                self._build_result(
                    "preprocessing.spam.mass_mentions",
                    spam.mass_mentions,
                    {"mention_count": features.mention_count},
                ),
            )

        if self._is_threshold_reached(spam.caps, features.uppercase_ratio, text_length=features.text_length):
            matches.append(
                self._build_result(
                    "preprocessing.spam.caps",
                    spam.caps,
                    {"uppercase_ratio": features.uppercase_ratio, "text_length": features.text_length},
                ),
            )

        if self._is_threshold_reached(spam.emoji, features.emoji_ratio, text_length=features.text_length):
            matches.append(
                self._build_result(
                    "preprocessing.spam.emoji",
                    spam.emoji,
                    {"emoji_ratio": features.emoji_ratio, "text_length": features.text_length},
                ),
            )

        if self._is_threshold_reached(
            spam.repeated_chars,
            features.repeated_char_score,
            text_length=features.text_length,
        ):
            matches.append(
                self._build_result(
                    "preprocessing.spam.repeated_chars",
                    spam.repeated_chars,
                    {"repeated_char_score": features.repeated_char_score, "text_length": features.text_length},
                ),
            )

        return matches

    def _evaluate_invite(self, context: MessageContext) -> list[PreprocessingRuleResult]:
        invite_policy = self._settings.invite

        if not invite_policy.detected.enabled or not context.invites:
            return []

        blocked_invites = tuple(
            invite for invite in context.invites if invite.lower() not in invite_policy.allowed_invite_codes
        )

        if not blocked_invites:
            return []

        return [
            self._build_result(
                "preprocessing.invite.detected",
                invite_policy.detected,
                {
                    "invites": context.invites,
                    "blocked_invites": blocked_invites,
                    "allowed_invite_codes": invite_policy.allowed_invite_codes,
                },
            ),
        ]

    def _evaluate_links(self, context: MessageContext) -> list[PreprocessingRuleResult]:
        features = context.features
        assert features is not None

        matches: list[PreprocessingRuleResult] = []
        link_policy = self._settings.links
        untrusted_domains = self._filter_untrusted_domains(context.domains, link_policy.allowed_domains)

        if link_policy.detect_any_url.enabled and features.has_url and untrusted_domains:
            matches.append(
                self._build_result(
                    "preprocessing.url.detected",
                    link_policy.detect_any_url,
                    {
                        "domains": context.domains,
                        "untrusted_domains": untrusted_domains,
                        "allowed_domains": link_policy.allowed_domains,
                    },
                ),
            )

        shortener_domains = tuple(
            domain
            for domain in context.domains
            if self._domain_matches_any(domain, link_policy.shortener_domains)
            and not self._domain_matches_any(domain, link_policy.allowed_domains)
        )

        if link_policy.shortener.enabled and features.has_shortener and shortener_domains:
            matches.append(
                self._build_result(
                    "preprocessing.url.shortener",
                    link_policy.shortener,
                    {
                        "domains": context.domains,
                        "shortener_domains": shortener_domains,
                        "allowed_domains": link_policy.allowed_domains,
                    },
                ),
            )

        return matches

    def _evaluate_evasion(self, context: MessageContext) -> list[PreprocessingRuleResult]:
        features = context.features
        assert features is not None

        evasion = self._settings.evasion.unicode

        if not evasion.enabled or not (features.has_mixed_scripts or features.has_suspicious_unicode):
            return []

        return [
            self._build_result(
                "preprocessing.evasion.unicode",
                evasion,
                {
                    "has_mixed_scripts": features.has_mixed_scripts,
                    "has_suspicious_unicode": features.has_suspicious_unicode,
                },
            ),
        ]

    def _build_result(
        self,
        rule_id: str,
        policy: PreprocessingRulePolicy,
        evidence: dict[str, Any],
    ) -> PreprocessingRuleResult:
        return PreprocessingRuleResult(
            rule_id=rule_id,
            labels=policy.labels,
            severity=policy.severity,
            confidence=policy.confidence,
            reason=policy.reason,
            risk_weight=policy.risk_weight,
            evidence=evidence,
        )

    def _is_threshold_reached(
        self,
        policy: PreprocessingRulePolicy,
        value: float | int,
        *,
        text_length: int | None = None,
    ) -> bool:
        if not policy.enabled or policy.threshold is None:
            return False

        if text_length is not None and text_length < policy.minimum_text_length:
            return False

        return value >= policy.threshold

    def _filter_untrusted_domains(
        self,
        domains: tuple[str, ...],
        allowed_domains: tuple[str, ...],
    ) -> tuple[str, ...]:
        return tuple(domain for domain in domains if not self._domain_matches_any(domain, allowed_domains))

    def _domain_matches_any(self, domain: str, patterns: tuple[str, ...]) -> bool:
        normalized_domain = domain.lower().removeprefix("www.")
        return any(
            normalized_domain == pattern or normalized_domain.endswith(f".{pattern}")
            for pattern in patterns
        )
