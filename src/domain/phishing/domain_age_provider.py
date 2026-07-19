from __future__ import annotations

from typing import Protocol

from src.domain.dto.phishing.domain_age_lookup_result import DomainAgeLookupResult


class DomainAgeProvider(Protocol):
    async def lookup(self, domain: str) -> DomainAgeLookupResult:
        """Return the registration age for a normalized domain."""
