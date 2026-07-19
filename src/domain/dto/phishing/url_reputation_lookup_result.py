from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UrlReputationLookupResult:
    url: str
    is_listed: bool
    threat_types: tuple[str, ...]
    source: str
