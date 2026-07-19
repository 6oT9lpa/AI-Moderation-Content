from __future__ import annotations

from typing import Protocol

from src.domain.dto.phishing.url_reputation_lookup_result import UrlReputationLookupResult


class UrlReputationProvider(Protocol):
    async def lookup(self, url: str) -> UrlReputationLookupResult:
        """Return the registry verdict for a URL."""
