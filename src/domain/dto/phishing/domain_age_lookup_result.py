from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DomainAgeLookupResult:
    domain: str
    age_days: int | None
    source: str
