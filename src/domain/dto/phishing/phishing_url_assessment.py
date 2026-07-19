from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PhishingUrlAssessment:
    domain: str
    domain_age_days: int | None
    registry_listed: bool | None
    registry_source: str | None
    registry_threat_types: tuple[str, ...]
    indicators: tuple[str, ...]
