from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from src.domain.dto.phishing.domain_age_lookup_result import DomainAgeLookupResult


class RdapDomainAgeProvider:
    API_URL = "https://rdap.org/domain/"

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    async def lookup(self, domain: str) -> DomainAgeLookupResult:
        payload = await asyncio.to_thread(self._request, domain)
        registered_at = self._find_registration_time(payload)
        age_days = None
        if registered_at is not None:
            age_days = max((datetime.now(timezone.utc) - registered_at).days, 0)
        return DomainAgeLookupResult(domain=domain, age_days=age_days, source="rdap")

    def _request(self, domain: str) -> dict[str, Any]:
        request = Request(f"{self.API_URL}{quote(domain, safe='')}", method="GET")
        with urlopen(request, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if not isinstance(payload, dict):
            raise ValueError("RDAP response must be an object")
        return payload

    @staticmethod
    def _find_registration_time(payload: dict[str, Any]) -> datetime | None:
        events = payload.get("events", [])
        if not isinstance(events, list):
            return None

        for event in events:
            if not isinstance(event, dict) or event.get("eventAction") != "registration":
                continue
            raw_value = event.get("eventDate")
            if not isinstance(raw_value, str):
                continue
            return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        return None
