from __future__ import annotations

import pytest

from src.modules.preprocessing import UrlExtractor


def test_extract_urls_deduplicates_and_strips_trailing_punctuation() -> None:
    text = "Go https://example.com/path?x=1, mirror www.test.org/a. Again https://example.com/path?x=1"

    urls = UrlExtractor.extract_urls(text)

    assert urls == (
        "https://example.com/path?x=1",
        "www.test.org/a",
    )


def test_extract_domains_normalizes_www_prefix() -> None:
    domains = UrlExtractor.extract_domains(
        (
            "https://www.example.com/path",
            "discord.gg/AbC123",
            "www.test.org/a",
        )
    )

    assert domains == ("example.com", "discord.gg", "test.org")


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
    assert UrlExtractor.extract_discord_invites(text) == (expected_code,)
    assert UrlExtractor.has_discord_invite(text) is True
    assert UrlExtractor.has_obfuscated_discord_invite(text) is False


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
    assert UrlExtractor.extract_discord_invites(text) == (expected_code,)
    assert UrlExtractor.has_discord_invite(text) is True
    assert UrlExtractor.has_obfuscated_discord_invite(text) is True


def test_extract_discord_invites_deduplicates_codes_preserving_order() -> None:
    text = "discord.gg/One discord.com/invite/Two discord[.]gg/One"

    assert UrlExtractor.extract_discord_invites(text) == ("one", "two")


def test_has_discord_invite_returns_false_for_plain_text() -> None:
    assert UrlExtractor.extract_discord_invites("no invite here") == ()
    assert UrlExtractor.has_discord_invite("no invite here") is False
    assert UrlExtractor.has_obfuscated_discord_invite("no invite here") is False
