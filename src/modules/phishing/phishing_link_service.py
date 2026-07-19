from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from src.domain.dto.phishing.domain_age_lookup_result import DomainAgeLookupResult
from src.domain.dto.phishing.phishing_url_assessment import PhishingUrlAssessment
from src.domain.dto.phishing.url_reputation_lookup_result import UrlReputationLookupResult
from src.domain.message_context import MessageContext
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.phishing.domain_age_provider import DomainAgeProvider
from src.domain.phishing.url_reputation_provider import UrlReputationProvider
from src.domain.rules.moderation_signal import ModerationSignal
from src.domain.rules.signal_source import SignalSource
from src.contracts.rules.phishing_policy import PhishingPolicy
from src.infrastructure.logging import get_logger
from src.modules.phishing.url_indicator_analyzer import UrlIndicatorAnalyzer

logger = get_logger(__name__)


class PhishingLinkService:
    def __init__(
        self,
        *,
        domain_age_provider: DomainAgeProvider | None,
        reputation_provider: UrlReputationProvider | None,
        indicator_analyzer: UrlIndicatorAnalyzer | None = None,
    ) -> None:
        self._domain_age_provider = domain_age_provider
        self._reputation_provider = reputation_provider
        self._indicator_analyzer = indicator_analyzer or UrlIndicatorAnalyzer()

    async def build_signals(
        self,
        context: MessageContext,
        existing_signals: list[ModerationSignal],
        policy: PhishingPolicy,
    ) -> list[ModerationSignal]:
        if not policy.enabled or not context.urls:
            return []

        if not self._has_scam_signal(existing_signals):
            logger.info("Phishing check skipped message_id=%s reason=no_scam_signal", context.message_id)
            return []

        if self._domain_age_provider is None or self._reputation_provider is None:
            logger.warning(
                "Phishing check skipped message_id=%s reason=provider_not_configured",
                context.message_id,
            )
            return []

        urls = context.urls[: policy.max_urls_per_message]
        assessments = await asyncio.gather(
            *(self._assess_url(url, context, policy) for url in urls),
        )
        signals = [
            self._to_signal(assessment, policy)
            for assessment in assessments
            if self._matches_policy(assessment, policy)
        ]
        if signals:
            logger.warning(
                "Phishing signal emitted message_id=%s matching_urls=%s",
                context.message_id,
                len(signals),
            )
        return signals

    async def _assess_url(
        self,
        url: str,
        context: MessageContext,
        policy: PhishingPolicy,
    ) -> PhishingUrlAssessment:
        domain = self._resolve_domain(url, context)
        if domain is None:
            return PhishingUrlAssessment(
                domain="",
                domain_age_days=None,
                registry_listed=None,
                registry_source=None,
                registry_threat_types=(),
                indicators=self._indicator_analyzer.analyze(url, context, policy),
            )

        age_result, reputation_result = await asyncio.gather(
            self._lookup_domain_age(domain, context.message_id),
            self._lookup_reputation(url, context.message_id),
        )
        return PhishingUrlAssessment(
            domain=domain,
            domain_age_days=age_result.age_days if age_result else None,
            registry_listed=reputation_result.is_listed if reputation_result else None,
            registry_source=reputation_result.source if reputation_result else None,
            registry_threat_types=reputation_result.threat_types if reputation_result else (),
            indicators=self._indicator_analyzer.analyze(url, context, policy),
        )

    async def _lookup_domain_age(
        self,
        domain: str,
        message_id: str,
    ) -> DomainAgeLookupResult | None:
        assert self._domain_age_provider is not None
        try:
            return await self._domain_age_provider.lookup(domain)
        except Exception:
            logger.warning("Domain age lookup failed message_id=%s domain=%s", message_id, domain, exc_info=True)
            return None

    async def _lookup_reputation(
        self,
        url: str,
        message_id: str,
    ) -> UrlReputationLookupResult | None:
        assert self._reputation_provider is not None
        try:
            return await self._reputation_provider.lookup(url)
        except Exception:
            logger.warning("URL reputation lookup failed message_id=%s", message_id, exc_info=True)
            return None

    @staticmethod
    def _has_scam_signal(signals: list[ModerationSignal]) -> bool:
        return any(signal.label == ModerationLabel.SCAM for signal in signals)

    @staticmethod
    def _resolve_domain(url: str, context: MessageContext) -> str | None:
        host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
        return host if host in context.domains else None

    @staticmethod
    def _matches_policy(assessment: PhishingUrlAssessment, policy: PhishingPolicy) -> bool:
        if assessment.registry_listed is True:
            return True

        return (
            assessment.domain_age_days is not None
            and assessment.domain_age_days <= policy.domain_max_age_days
            and assessment.registry_listed is False
            and len(assessment.indicators) >= policy.minimum_bad_indicators
        )

    @staticmethod
    def _to_signal(assessment: PhishingUrlAssessment, policy: PhishingPolicy) -> ModerationSignal:
        return ModerationSignal(
            source=SignalSource.PHISHING,
            label=ModerationLabel.SCAM,
            confidence=policy.confidence,
            severity=policy.severity,
            risk_weight=policy.risk_weight,
            reason=policy.reason,
            rule_id="phishing.url_assessment",
            evidence={
                "domain": assessment.domain,
                "domain_age_days": assessment.domain_age_days,
                "registry_listed": assessment.registry_listed,
                "registry_source": assessment.registry_source,
                "registry_threat_types": assessment.registry_threat_types,
                "indicators": assessment.indicators,
            },
        )
