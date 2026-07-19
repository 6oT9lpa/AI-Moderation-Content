from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlsplit

from src.contracts.rules.phishing_policy import PhishingPolicy
from src.domain.message_context import MessageContext


class UrlIndicatorAnalyzer:
    def analyze(
        self,
        url: str,
        context: MessageContext,
        policy: PhishingPolicy,
    ) -> tuple[str, ...]:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        indicators: list[str] = []

        if context.has_shortener:
            indicators.append("url_shortener")
        if host.startswith("xn--") or ".xn--" in host:
            indicators.append("punycode_domain")
        if self._is_ip_address(host):
            indicators.append("ip_address_host")
        if host and len(host.split(".")) > policy.max_domain_labels:
            indicators.append("excessive_domain_labels")

        candidate = f"{host}{parsed.path}".lower()
        if any(keyword in candidate for keyword in policy.suspicious_keywords):
            indicators.append("suspicious_keyword")

        return tuple(indicators)

    @staticmethod
    def _is_ip_address(host: str) -> bool:
        try:
            ip_address(host)
        except ValueError:
            return False
        return True
