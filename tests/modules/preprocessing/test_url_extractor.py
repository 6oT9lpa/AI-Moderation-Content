from __future__ import annotations

import pytest

from src.infrastructure.logging import get_logger
from src.modules.preprocessing.url_extractor import UrlExtractor

logger = get_logger("tests.preprocessing")


def test_extract_urls_detects_links_and_domains() -> None:
    text = "go to https://example.com/path, www.test.ru and domain.org/page"

    urls = UrlExtractor.extract_urls(text)

    logger.info("URL extraction text=%r urls=%s", text, urls)

    assert urls == (
        "https://example.com/path",
        "www.test.ru",
        "domain.org/page",
    )


def test_extract_domains_normalizes_www_prefix() -> None:
    urls = (
        "https://www.example.com/path",
        "www.test.ru/page",
        "domain.org/path",
    )

    domains = UrlExtractor.extract_domains(urls)

    logger.info("Domain extraction urls=%s domains=%s", urls, domains)

    assert domains == ("example.com", "test.ru", "domain.org")


@pytest.mark.parametrize(
    ("text", "expected_code"),
    [
        ("join discord.gg/AbC123", "abc123"),
        ("join https://discord.gg/AbC_123", "abc_123"),
        ("join www.discord.gg/AbC-123", "abc-123"),
        ("join discord.com/invite/InviteCode", "invitecode"),
        ("join https://discordapp.com/invite/legacy", "legacy"),
        ("join https://canary.discord.com/invite/canary", "canary"),
        ("join https://ptb.discord.com/invite/ptb-code", "ptb-code"),
    ],
)
def test_extract_discord_invites_detects_regular_invite_variants(
    text: str,
    expected_code: str,
) -> None:
    invites = UrlExtractor.extract_discord_invites(text)
    has_invite = UrlExtractor.has_discord_invite(text)
    has_obfuscated = UrlExtractor.has_obfuscated_discord_invite(text)

    logger.info(
        "Regular invite extraction text=%r invites=%s has_invite=%s has_obfuscated=%s",
        text,
        invites,
        has_invite,
        has_obfuscated,
    )

    assert invites == (expected_code,)
    assert has_invite is True
    assert has_obfuscated is False


@pytest.mark.parametrize(
    ("text", "expected_code"),
    [
        ("join discord . gg/Hidden123", "hidden123"),
        ("join discord[.]gg/Hidden123", "hidden123"),
        ("join discord(.)gg/Hidden123", "hidden123"),
        ("join discord dot gg/Hidden123", "hidden123"),
        (r"join discord.gg\\Hidden123", "hidden123"),
    ],
)
def test_extract_discord_invites_detects_obfuscated_invites(
    text: str,
    expected_code: str,
) -> None:
    invites = UrlExtractor.extract_discord_invites(text)
    has_invite = UrlExtractor.has_discord_invite(text)
    has_obfuscated = UrlExtractor.has_obfuscated_discord_invite(text)

    logger.info(
        "Obfuscated invite extraction text=%r invites=%s has_invite=%s has_obfuscated=%s",
        text,
        invites,
        has_invite,
        has_obfuscated,
    )

    assert invites == (expected_code,)
    assert has_invite is True
    assert has_obfuscated is True


def test_extract_discord_invites_removes_duplicates() -> None:
    text = "discord.gg/SameCode discord.com/invite/SameCode discord[.]gg/SameCode"

    invites = UrlExtractor.extract_discord_invites(text)

    logger.info("Duplicate invite extraction text=%r invites=%s", text, invites)

    assert invites == ("samecode",)


def test_has_discord_invite_returns_false_for_safe_text() -> None:
    text = "hello world without invite"

    logger.info("Safe invite check text=%r", text)

    assert UrlExtractor.extract_discord_invites(text) == ()
    assert UrlExtractor.has_discord_invite(text) is False
    assert UrlExtractor.has_obfuscated_discord_invite(text) is False
