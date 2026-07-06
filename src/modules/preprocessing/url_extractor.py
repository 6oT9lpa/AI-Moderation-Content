from __future__ import annotations

import re
from urllib.parse import urlparse

_URL_RE = re.compile(
    r"(?i)\b(?:https?://|www\.)[^\s<>()]+|\b[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+(?:/[^\s<>()]*)?"
)

_DISCORD_INVITE_RE = re.compile(
    r"""
    (?ix)
    \b
    (?:
        (?:https?://)?
        (?:www\.)?
        (?:
            discord\.gg
            |
            discord(?:app)?\.com/invite
            |
            canary\.discord\.com/invite
            |
            ptb\.discord\.com/invite
        )
        /
        (?P<code>[a-z0-9_-]{2,64})
    )
    (?=$|[\s?#/&.,!)]|\b)
    """
)

_OBFUSCATED_DISCORD_INVITE_RE = re.compile(
    r"""
    (?ix)
    \b
    discord
    \s*
    (?:
        \.
        |
        \[\s*\.\s*\]
        |
        \(\s*\.\s*\)
        |
        dot
    )
    \s*
    gg
    \s*
    [\/\\]
    \s*
    (?P<code>[a-z0-9_-]{2,64})
    """
)

_TRAILING_PUNCTUATION = ".,!?;:)]}>'\""


class UrlExtractor:
    @staticmethod
    def extract_urls(text: str) -> tuple[str, ...]:
        urls: list[str] = []

        for match in _URL_RE.finditer(text or ""):
            url = match.group(0).strip().rstrip(_TRAILING_PUNCTUATION)

            if url and url not in urls:
                urls.append(url)

        return tuple(urls)

    @staticmethod
    def extract_domains(urls: tuple[str, ...]) -> tuple[str, ...]:
        domains: list[str] = []

        for url in urls:
            parsed_url = url if "://" in url else f"https://{url}"
            netloc = urlparse(parsed_url).netloc.lower()

            if netloc.startswith("www."):
                netloc = netloc[4:]

            if netloc and netloc not in domains:
                domains.append(netloc)

        return tuple(domains)

    @staticmethod
    def has_discord_invite(text: str) -> bool:
        return bool(
            _DISCORD_INVITE_RE.search(text or "")
            or _OBFUSCATED_DISCORD_INVITE_RE.search(text or "")
        )

    @staticmethod
    def has_obfuscated_discord_invite(text: str) -> bool:
        return bool(_OBFUSCATED_DISCORD_INVITE_RE.search(text or ""))

    @staticmethod
    def extract_discord_invites(text: str) -> tuple[str, ...]:
        invites: list[str] = []

        for match in _DISCORD_INVITE_RE.finditer(text or ""):
            invite_code = match.group("code").lower()

            if invite_code and invite_code not in invites:
                invites.append(invite_code)

        for match in _OBFUSCATED_DISCORD_INVITE_RE.finditer(text or ""):
            invite_code = match.group("code").lower()

            if invite_code and invite_code not in invites:
                invites.append(invite_code)

        return tuple(invites)