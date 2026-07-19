from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.domain.dto.phishing.url_reputation_lookup_result import UrlReputationLookupResult


class GoogleSafeBrowsingUrlReputationProvider:
    API_URL = "https://safebrowsing.googleapis.com/v5/urls:search"

    def __init__(self, api_key: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    async def lookup(self, url: str) -> UrlReputationLookupResult:
        payload = await asyncio.to_thread(self._request, url)
        threats = payload.get("threats", [])
        if not isinstance(threats, list):
            raise ValueError("Google Safe Browsing response has invalid threats field")

        threat_types = tuple(
            str(threat_type)
            for threat in threats
            if isinstance(threat, dict)
            for threat_type in threat.get("threatTypes", [])
        )
        return UrlReputationLookupResult(
            url=url,
            is_listed=bool(threats),
            threat_types=tuple(dict.fromkeys(threat_types)),
            source="google_safe_browsing",
        )

    def _request(self, url: str) -> dict[str, Any]:
        query = urlencode({"key": self._api_key, "urls[]": url})
        request = Request(f"{self.API_URL}?{query}", method="GET")
        with urlopen(request, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if not isinstance(payload, dict):
            raise ValueError("Google Safe Browsing response must be an object")
        return payload
