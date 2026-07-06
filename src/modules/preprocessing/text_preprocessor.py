from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from src.contracts import MessagePreprocessInputSchema
from src.domain import MessageContext
from src.modules.preprocessing import TextFeatureExtractor
from src.modules.preprocessing import TextNormalizer
from src.modules.preprocessing import UrlExtractor


class TextPreprocessor:
    DEFAULT_SHORTENER_DOMAINS = frozenset(
        {
            "bit.ly",
            "t.co",
            "tinyurl.com",
            "goo.gl",
            "cutt.ly",
            "is.gd",
            "s.id",
            "clck.ru",
            "vk.cc",
            "ow.ly",
            "shorturl.at",
            "rebrand.ly",
        }
    )

    def __init__(self, *, shortener_domains: set[str] | frozenset[str] | None = None) -> None:
        self.shortener_domains = frozenset(shortener_domains or self.DEFAULT_SHORTENER_DOMAINS)

    async def process(self, payload: MessagePreprocessInputSchema) -> MessageContext:
        raw_text = payload.raw_text or ""
        normalized_text = TextNormalizer.normalize(raw_text)

        urls = UrlExtractor.extract_urls(raw_text)
        domains = UrlExtractor.extract_domains(urls)
        invites = UrlExtractor.extract_discord_invites(raw_text)
        has_shortener = any(domain in self.shortener_domains for domain in domains)

        features = TextFeatureExtractor.extract(
            raw_text,
            urls=urls,
            invites=invites,
            has_shortener=has_shortener,
            mention_count=payload.mention_count,
            role_mention_count=payload.role_mention_count,
            channel_mention_count=payload.channel_mention_count,
        )

        return MessageContext(
            platform=payload.platform,
            guild_id=payload.guild_id,
            channel_id=payload.channel_id,
            user_id=payload.user_id,
            message_id=payload.message_id,
            created_at=payload.created_at,
            raw_text=raw_text,
            normalized_text=normalized_text,
            text_hash=self._hash_text(normalized_text),
            language=self._detect_language(features.has_cyrillic, features.has_latin),
            reply_to_message_id=payload.reply_to_message_id,
            urls=urls,
            domains=domains,
            invites=invites,
            has_url=features.has_url,
            has_invite=features.has_invite,
            has_shortener=features.has_shortener,
            has_attachments=payload.has_attachments,
            attachment_count=payload.attachment_count,
            account_age_days=self._calculate_age_days(payload.author_created_at, payload.created_at),
            member_age_days=self._calculate_age_days(payload.member_joined_at, payload.created_at),
            recent_messages=payload.recent_messages,
            features=features,
            metadata={
                **payload.metadata,
                "feature_version": "text_preprocessor_v1",
            },
        )

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _detect_language(has_cyrillic: bool, has_latin: bool) -> str:
        if has_cyrillic and has_latin:
            return "mixed"
        if has_cyrillic:
            return "ru"
        if has_latin:
            return "en"
        return "unknown"

    @staticmethod
    def _calculate_age_days(started_at: datetime | None, current_at: datetime) -> int | None:
        if started_at is None:
            return None

        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        if current_at.tzinfo is None:
            current_at = current_at.replace(tzinfo=timezone.utc)

        return max((current_at - started_at).days, 0)
