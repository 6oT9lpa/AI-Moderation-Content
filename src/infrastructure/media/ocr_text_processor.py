import hashlib
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ProcessedOcrText:
    normalized_text: str
    redacted_text: str
    text_hash: str | None
    language: str | None
    flags: tuple[str, ...]


class OcrTextProcessor:
    _ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
    _CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    _WHITESPACE = re.compile(r"[ \t\f\v]+")
    _NEWLINES = re.compile(r"\s*\n\s*")
    _EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,63}")
    _PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)")
    _CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
    _TOKEN = re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*[A-Za-z0-9_./+\-=]{8,}")
    _WALLET = re.compile(r"\b(?:0x[a-fA-F0-9]{40}|bc1[a-zA-HJ-NP-Z0-9]{25,90}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
    _URL = re.compile(r"https?://[^\s<>]{1,2048}", re.IGNORECASE)
    _PROMPT_INJECTION = re.compile(
        r"(?i)(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|system)\s+(?:instructions?|prompts?)"
    )

    def __init__(self, max_length: int) -> None:
        self._max_length = max_length

    def process(self, text: str) -> ProcessedOcrText:
        normalized = self._normalize(text)[: self._max_length]
        if not normalized:
            return ProcessedOcrText("", "", None, None, ())

        flags: list[str] = []
        redacted = normalized
        redacted, matched = self._replace(redacted, self._EMAIL, "[EMAIL]")
        if matched:
            flags.append("email")
        redacted, card_found = self._redact_cards(redacted)
        if card_found:
            flags.append("payment_card")
        redacted, matched = self._replace(redacted, self._PHONE, "[PHONE]")
        if matched:
            flags.append("phone")
        redacted, matched = self._replace(redacted, self._TOKEN, "[ACCESS_SECRET]")
        if matched:
            flags.append("access_secret")
        redacted, matched = self._replace(redacted, self._WALLET, "[PAYMENT_WALLET]")
        if matched:
            flags.append("payment_wallet")
        redacted, sensitive_url = self._redact_urls(redacted)
        if sensitive_url:
            flags.append("sensitive_url")
        if self._PROMPT_INJECTION.search(normalized):
            flags.append("prompt_injection")

        return ProcessedOcrText(
            normalized_text=normalized,
            redacted_text=redacted,
            text_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            language=self._detect_language(normalized),
            flags=tuple(flags),
        )

    def _normalize(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text)
        normalized = self._ZERO_WIDTH.sub("", normalized)
        normalized = self._CONTROL.sub("", normalized)
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        normalized = self._WHITESPACE.sub(" ", normalized)
        normalized = self._NEWLINES.sub("\n", normalized)
        return normalized.strip()

    @staticmethod
    def _replace(text: str, pattern: re.Pattern[str], replacement: str) -> tuple[str, int]:
        return pattern.subn(replacement, text)[0:2]

    def _redact_cards(self, text: str) -> tuple[str, bool]:
        found = False

        def replacement(match: re.Match[str]) -> str:
            nonlocal found
            digits = "".join(character for character in match.group(0) if character.isdigit())
            if not self._passes_luhn(digits):
                return match.group(0)
            found = True
            return "[PAYMENT_CARD]"

        return self._CARD.sub(replacement, text), found

    def _redact_urls(self, text: str) -> tuple[str, bool]:
        sensitive = False

        def replacement(match: re.Match[str]) -> str:
            nonlocal sensitive
            parsed = urlsplit(match.group(0))
            if parsed.query or parsed.fragment or parsed.username or parsed.password:
                sensitive = True
            host = (parsed.hostname or "unknown").casefold().rstrip(".")
            return f"[URL:{host}]"

        return self._URL.sub(replacement, text), sensitive

    @staticmethod
    def _passes_luhn(digits: str) -> bool:
        if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
            return False
        checksum = 0
        parity = len(digits) % 2
        for index, digit in enumerate(digits):
            value = int(digit)
            if index % 2 == parity:
                value *= 2
                if value > 9:
                    value -= 9
            checksum += value
        return checksum % 10 == 0

    @staticmethod
    def _detect_language(text: str) -> str | None:
        cyrillic = sum("а" <= character.casefold() <= "я" or character.casefold() == "ё" for character in text)
        latin = sum("a" <= character.casefold() <= "z" for character in text)
        if cyrillic and latin:
            return "ru-en"
        if cyrillic:
            return "ru"
        if latin:
            return "en"
        return None
