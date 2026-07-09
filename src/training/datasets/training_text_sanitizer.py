from __future__ import annotations

import re
from urllib.parse import urlparse


class TrainingTextSanitizer:
    URL_RE = re.compile(r"(?i)<?\b(?:https?://|www\.)[^\s<>]+>?|(?<!@)\b[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s<>]*)?")
    EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])", re.IGNORECASE)
    PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
    SECRET_RE = re.compile(r"(?i)\b(?:token|api[_-]?key|secret|password)\s*[:=]\s*[^\s,;]{6,}")
    WHITESPACE_RE = re.compile(r"\s+")
    DISCORD_USER_MENTION_RE = re.compile(r"<@!?\d{5,25}>")
    DISCORD_ROLE_MENTION_RE = re.compile(r"<@&\d{5,25}>")
    DISCORD_CHANNEL_MENTION_RE = re.compile(r"<#\d{5,25}>")
    TOKEN_RE = re.compile(
        r"(?i)<(?:URL_DOMAIN:[a-z0-9.-]+|DISCORD_INVITE|DISCORD_USER_MENTION|"
        r"DISCORD_ROLE_MENTION|DISCORD_CHANNEL_MENTION|EMAIL|PHONE|SECRET|URL)>"
    )

    DISCORD_INVITE_RE = re.compile(
        r"(?i)(?:https?://)?(?:discord\.gg|discord(?:app)?\.com/invite)/[a-z0-9_-]+"
    )

    def sanitize(self, text: str) -> str:
        protected: dict[str, str] = {}
        result = self._protect_tokens(text, protected).casefold()
        result = self.SECRET_RE.sub("<SECRET>", result)
        result = self.DISCORD_ROLE_MENTION_RE.sub("<DISCORD_ROLE_MENTION>", result)
        result = self.DISCORD_CHANNEL_MENTION_RE.sub("<DISCORD_CHANNEL_MENTION>", result)
        result = self.DISCORD_USER_MENTION_RE.sub("<DISCORD_USER_MENTION>", result)
        result = self.EMAIL_RE.sub("<EMAIL>", result)
        result = self.DISCORD_INVITE_RE.sub("<DISCORD_INVITE>", result)
        result = self.URL_RE.sub(lambda match: self._url_token(match.group(0)), result)
        result = self.PHONE_RE.sub("<PHONE>", result)
        result = self._restore_tokens(result, protected)
        return self.WHITESPACE_RE.sub(" ", result).strip()

    def _protect_tokens(self, text: str, protected: dict[str, str]) -> str:
        def replace(match: re.Match[str]) -> str:
            key = f"__sanitized_token_{len(protected)}__"
            protected[key] = self._canonical_token(match.group(0))
            return key

        return self.TOKEN_RE.sub(replace, text)

    def _restore_tokens(self, text: str, protected: dict[str, str]) -> str:
        result = text
        for key, token in protected.items():
            result = result.replace(key, token)
        return result

    def _canonical_token(self, token: str) -> str:
        value = token.strip()
        if value.casefold().startswith("<url_domain:"):
            domain = value[len("<URL_DOMAIN:") : -1].casefold()
            return f"<URL_DOMAIN:{domain}>"

        return value.upper()

    def _url_token(self, value: str) -> str:
        domain = self._extract_domain(value)
        if domain:
            return f"<URL_DOMAIN:{domain}>"

        return "<URL>"

    def _extract_domain(self, value: str) -> str:
        value = value.strip("<>")
        parsed = urlparse(value if "://" in value else f"https://{value}")
        domain = (parsed.netloc or parsed.path.split("/", 1)[0]).lower().removeprefix("www.")
        return domain if re.fullmatch(r"[a-z0-9.-]{1,253}", domain) else ""
