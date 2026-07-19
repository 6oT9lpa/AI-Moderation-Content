from __future__ import annotations

from datetime import datetime, timezone

from src.domain.dto.phishing.domain_age_lookup_result import DomainAgeLookupResult
from src.domain.dto.phishing.url_reputation_lookup_result import UrlReputationLookupResult
from src.domain.message_context import MessageContext
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.moderation_signal import ModerationSignal
from src.domain.rules.signal_source import SignalSource
from src.contracts.rules.phishing_policy import PhishingPolicy
from src.modules.phishing.phishing_link_service import PhishingLinkService
from src.modules.rules.moderation_rule_policy_config_loader import ModerationRulePolicyConfigLoader


class _DomainAgeProviderStub:
    def __init__(self, age_days: int | None) -> None:
        self._age_days = age_days

    async def lookup(self, domain: str) -> DomainAgeLookupResult:
        return DomainAgeLookupResult(domain=domain, age_days=self._age_days, source="stub_rdap")


class _ReputationProviderStub:
    def __init__(self, is_listed: bool) -> None:
        self._is_listed = is_listed

    async def lookup(self, url: str) -> UrlReputationLookupResult:
        return UrlReputationLookupResult(
            url=url,
            is_listed=self._is_listed,
            threat_types=("SOCIAL_ENGINEERING",) if self._is_listed else (),
            source="stub_registry",
        )


async def test_phishing_service_emits_scam_signal_for_fresh_unlisted_suspicious_url() -> None:
    service = PhishingLinkService(
        domain_age_provider=_DomainAgeProviderStub(age_days=3),
        reputation_provider=_ReputationProviderStub(is_listed=False),
    )

    signals = await service.build_signals(
        _context("https://claim-wallet.example/login"),
        [_scam_signal()],
        PhishingPolicy(enabled=True),
    )

    assert len(signals) == 1
    assert signals[0].source == SignalSource.PHISHING
    assert signals[0].label == ModerationLabel.SCAM
    assert signals[0].evidence["domain_age_days"] == 3
    assert signals[0].evidence["registry_listed"] is False
    assert "suspicious_keyword" in signals[0].evidence["indicators"]


async def test_phishing_service_emits_scam_signal_for_registry_match() -> None:
    service = PhishingLinkService(
        domain_age_provider=_DomainAgeProviderStub(age_days=3),
        reputation_provider=_ReputationProviderStub(is_listed=True),
    )

    signals = await service.build_signals(
        _context("https://claim-wallet.example/login"),
        [_scam_signal()],
        PhishingPolicy(enabled=True),
    )

    assert len(signals) == 1
    assert signals[0].evidence["registry_listed"] is True


async def test_phishing_service_requires_existing_scam_signal() -> None:
    service = PhishingLinkService(
        domain_age_provider=_DomainAgeProviderStub(age_days=3),
        reputation_provider=_ReputationProviderStub(is_listed=False),
    )

    signals = await service.build_signals(
        _context("https://claim-wallet.example/login"),
        [],
        PhishingPolicy(enabled=True),
    )

    assert signals == []


def test_default_moderation_policy_contains_disabled_phishing_rule() -> None:
    policy = ModerationRulePolicyConfigLoader.load()

    assert policy.phishing.enabled is False
    assert policy.phishing.domain_max_age_days == 7


def _context(url: str) -> MessageContext:
    return MessageContext(
        platform="discord",
        guild_id="guild",
        channel_id="channel",
        user_id="user",
        message_id="message",
        created_at=datetime.now(timezone.utc),
        raw_text=url,
        normalized_text=url,
        text_hash="hash",
        language="en",
        urls=(url,),
        domains=("claim-wallet.example",),
        has_url=True,
    )


def _scam_signal() -> ModerationSignal:
    return ModerationSignal(
        source=SignalSource.RUBERT,
        label=ModerationLabel.SCAM,
        confidence=0.9,
        severity=4,
        risk_weight=50,
        reason="rubert_scam",
    )
