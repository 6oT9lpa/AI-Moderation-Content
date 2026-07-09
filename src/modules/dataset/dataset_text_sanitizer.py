from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from src.domain.dto.dataset.dataset_text_snapshot import DatasetTextSnapshot
from src.domain.message_context import MessageContext
from src.infrastructure.logging.logger import get_logger
from src.modules.preprocessing.url_extractor import UrlExtractor

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class _Replacement:
    pattern: re.Pattern[str]
    token: str
    kind: str


class DatasetTextSanitizer:
    EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])", re.IGNORECASE)
    PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
    SECRET_RE = re.compile(
        r"(?i)\b(?:token|api[_-]?key|secret|password)\s*[:=]\s*[^\s,;]{6,}"
    )
    DISCORD_USER_MENTION_RE = re.compile(r"<@!?\d{5,25}>")
    DISCORD_ROLE_MENTION_RE = re.compile(r"<@&\d{5,25}>")
    DISCORD_CHANNEL_MENTION_RE = re.compile(r"<#\d{5,25}>")
    TOKEN_RE = re.compile(
        r"(?i)<(?:URL_DOMAIN:[a-z0-9.-]+|DISCORD_INVITE|DISCORD_USER_MENTION|"
        r"DISCORD_ROLE_MENTION|DISCORD_CHANNEL_MENTION|EMAIL|PHONE|SECRET|URL)>"
    )
    CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    WHITESPACE_RE = re.compile(r"\s+")

    INJECTION_MARKERS = {
        "ignore_previous_instructions": re.compile(r"(?i)\bignore\s+(?:all\s+)?previous\s+instructions\b"),
        "system_prompt_reference": re.compile(r"(?i)\b(?:system|developer)\s+prompt\b"),
        "role_instruction": re.compile(r"(?i)\b(?:you\s+are|act\s+as)\s+(?:chatgpt|an?\s+ai|system)\b"),
        "safe_label_instruction": re.compile(r"(?i)\b(?:mark|classify|label)\s+(?:this\s+)?(?:as\s+)?safe\b"),
    }

    def build_snapshot(
        self,
        context: MessageContext,
        *,
        store_raw_text: bool = False,
    ) -> DatasetTextSnapshot:
        raw_text = context.raw_text or ""
        normalized_text = context.normalized_text or ""
        redactions: list[dict[str, Any]] = []

        redacted_text = self._strip_control_chars(normalized_text)
        protected_tokens: dict[str, str] = {}
        redacted_text = self._protect_tokens(redacted_text, protected_tokens)
        redacted_text = self._apply_static_replacements(redacted_text, redactions)
        redacted_text = self._replace_urls(redacted_text, context.urls, redactions)
        redacted_text = self._apply_phone_replacement(redacted_text, redactions)
        redacted_text = self._restore_tokens(redacted_text, protected_tokens)
        redacted_text = self._normalize_whitespace(redacted_text)

        injection_markers = self._detect_injection_markers(normalized_text)

        snapshot = DatasetTextSnapshot(
            raw_text=raw_text if store_raw_text else None,
            normalized_text=normalized_text,
            redacted_text=redacted_text,
            model_text=redacted_text,
            text_hash=context.text_hash,
            redactions=redactions,
            injection_markers=injection_markers,
        )
        logger.info(
            "Dataset text snapshot built message_id=%s redactions=%s injection_markers=%s",
            context.message_id,
            len(redactions),
            injection_markers,
        )
        return snapshot

    def _replace_urls(
        self,
        text: str,
        urls: tuple[str, ...],
        redactions: list[dict[str, Any]],
    ) -> str:
        result = text
        for url in sorted(urls, key=len, reverse=True):
            token = self._url_token(url)
            replaced = False
            if url in result:
                result = result.replace(url, token)
                replaced = True
            else:
                normalized_url = url.casefold()
                if normalized_url in result:
                    result = result.replace(normalized_url, token)
                    replaced = True

            if not replaced:
                continue

            redactions.append(
                {
                    "kind": "url",
                    "token": token,
                    "domain": self._safe_domain(self._extract_domain(url)),
                }
            )

        return result

    def _apply_static_replacements(
        self,
        text: str,
        redactions: list[dict[str, Any]],
    ) -> str:
        replacements = (
            _Replacement(self.SECRET_RE, "<SECRET>", "secret"),
            _Replacement(self.DISCORD_ROLE_MENTION_RE, "<DISCORD_ROLE_MENTION>", "discord_role_mention"),
            _Replacement(self.DISCORD_CHANNEL_MENTION_RE, "<DISCORD_CHANNEL_MENTION>", "discord_channel_mention"),
            _Replacement(self.DISCORD_USER_MENTION_RE, "<DISCORD_USER_MENTION>", "discord_user_mention"),
            _Replacement(self.EMAIL_RE, "<EMAIL>", "email"),
        )

        result = text
        for replacement in replacements:
            matches = replacement.pattern.findall(result)
            if not matches:
                continue

            result = replacement.pattern.sub(replacement.token, result)
            redactions.append(
                {
                    "kind": replacement.kind,
                    "token": replacement.token,
                    "count": len(matches),
                }
            )

        return result

    def _apply_phone_replacement(
        self,
        text: str,
        redactions: list[dict[str, Any]],
    ) -> str:
        matches = self.PHONE_RE.findall(text)
        if not matches:
            return text

        redactions.append(
            {
                "kind": "phone",
                "token": "<PHONE>",
                "count": len(matches),
            }
        )
        return self.PHONE_RE.sub("<PHONE>", text)

    def _protect_tokens(self, text: str, protected_tokens: dict[str, str]) -> str:
        def replace(match: re.Match[str]) -> str:
            key = f"__sanitized_token_{len(protected_tokens)}__"
            protected_tokens[key] = self._canonical_token(match.group(0))
            return key

        return self.TOKEN_RE.sub(replace, text)

    def _restore_tokens(self, text: str, protected_tokens: dict[str, str]) -> str:
        result = text
        for key, token in protected_tokens.items():
            result = result.replace(key, token)
        return result

    def _canonical_token(self, token: str) -> str:
        value = token.strip()
        if value.casefold().startswith("<url_domain:"):
            domain = value[len("<URL_DOMAIN:") : -1].casefold()
            return f"<URL_DOMAIN:{domain}>"

        return value.upper()

    def _url_token(self, url: str) -> str:
        domain = self._safe_domain(self._extract_domain(url))
        if self._is_discord_invite(url):
            return "<DISCORD_INVITE>"

        if domain:
            return f"<URL_DOMAIN:{domain}>"

        return "<URL>"

    def _extract_domain(self, url: str) -> str:
        try:
            url = url.strip("<>")
            parsed = urlparse(url if "://" in url else f"https://{url}")
        except ValueError:
            return ""

        return parsed.netloc or parsed.path.split("/", 1)[0]

    def _safe_domain(self, domain: str) -> str:
        normalized = domain.lower().removeprefix("www.")
        return normalized if re.fullmatch(r"[a-z0-9.-]{1,253}", normalized) else ""

    def _is_discord_invite(self, url: str) -> bool:
        return UrlExtractor.has_discord_invite(url) or UrlExtractor.has_obfuscated_discord_invite(url)

    def _detect_injection_markers(self, text: str) -> list[str]:
        return [
            marker
            for marker, pattern in self.INJECTION_MARKERS.items()
            if pattern.search(text)
        ]

    def _strip_control_chars(self, text: str) -> str:
        return self.CONTROL_RE.sub(" ", text)

    def _normalize_whitespace(self, text: str) -> str:
        return self.WHITESPACE_RE.sub(" ", text).strip()
