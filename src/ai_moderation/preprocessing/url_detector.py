from __future__ import annotations

import re
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict


class UrlDetection(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    has_url: bool = False
    has_invite: bool = False
    has_shortener: bool = False

    urls: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    invites: tuple[str, ...] = ()


class UrlDetector:
    URL_PATTERN = re.compile(
        r"""
        (?:
            https?://
            |
            ftp://
            |
            www\.
        )?
        (?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}
        (?::\d+)?
        (?:/[^\s<>"']*)?
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    INVITE_PATTERN = re.compile(
        r"""
        (?:
            https?://
        )?
        (?:
            discord(?:app)?\.com/invite/
            |
            discord\.gg/
        )
        ([A-Za-z0-9_-]+)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    SHORTENERS = frozenset({
        "bit.ly",
        "t.co",
        "goo.gl",
        "tinyurl.com",
        "is.gd",
        "cutt.ly",
        "clck.ru",
        "vk.cc",
        "rb.gy",
    })

    def detect(self, text: str) -> UrlDetection:
        if not text:
            return UrlDetection()

        urls = tuple(dict.fromkeys(
            match.group(0).rstrip(".,!?;:)")
            for match in self.URL_PATTERN.finditer(text)
        ))

        invites = tuple(dict.fromkeys(
            match.group(0).rstrip(".,!?;:)")
            for match in self.INVITE_PATTERN.finditer(text)
        ))

        domains: set[str] = set()
        has_shortener = False

        for url in urls:
            parsed = urlparse(url if "://" in url else f"https://{url}")

            domain = parsed.netloc.lower().removeprefix("www.")

            if not domain:
                continue

            domains.add(domain)

            if domain in self.SHORTENERS:
                has_shortener = True

        return UrlDetection(
            has_url=bool(urls),
            has_invite=bool(invites),
            has_shortener=has_shortener,
            urls=urls,
            domains=tuple(sorted(domains)),
            invites=invites,
        )