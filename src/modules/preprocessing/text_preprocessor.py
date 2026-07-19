from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from typing import Mapping

from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.domain.message_context import MessageContext
from src.infrastructure.logging import get_logger
from src.modules.preprocessing.detectors.mention_extractor import MentionExtractor
from src.modules.preprocessing.rules.preprocessing_rule_config_loader import PreprocessingRuleConfigLoader
from src.modules.preprocessing.rules.preprocessing_rule_engine import PreprocessingRuleEngine
from src.modules.preprocessing.rules.preprocessing_rule_settings import PreprocessingRuleSettings
from src.modules.preprocessing.text_feature_extractor import TextFeatureExtractor
from src.modules.preprocessing.text_normalizer import TextNormalizer
from src.modules.preprocessing.url_extractor import UrlExtractor

logger = get_logger(__name__)


class TextPreprocessor:
    def __init__(
        self,
        *,
        shortener_domains: set[str] | frozenset[str] | None = None,
        rule_settings: PreprocessingRuleSettings | None = None,
        rule_config_path: str = "configs/rules/preprocessing_rules.yaml",
    ) -> None:
        self._default_rule_settings = rule_settings or PreprocessingRuleConfigLoader().load(rule_config_path)
        self.shortener_domains = frozenset(
            domain.lower()
            for domain in (shortener_domains or self._default_rule_settings.links.shortener_domains)
        )
        self._rule_engine = PreprocessingRuleEngine(self._default_rule_settings)
        logger.info(
            "Text preprocessor initialized shortener_domains=%s rule_settings=%s",
            len(self.shortener_domains),
            self._default_rule_settings,
        )

    async def process(self, payload: MessagePreprocessInputSchema) -> MessageContext:
        logger.info(
            "Text preprocessing started platform=%s guild_id=%s channel_id=%s message_id=%s",
            payload.platform,
            payload.guild_id,
            payload.channel_id,
            payload.message_id,
        )
        raw_text = payload.raw_text or ""
        normalized_text = TextNormalizer.normalize(raw_text)

        urls = UrlExtractor.extract_urls(raw_text)
        domains = UrlExtractor.extract_domains(urls)
        invites = UrlExtractor.extract_discord_invites(raw_text)
        has_shortener = any(self._domain_matches_any(domain, self.shortener_domains) for domain in domains)
        mention_count, role_mention_count, channel_mention_count = self._resolve_mention_counts(payload)
        recent_activity = self._build_recent_activity(payload, normalized_text)

        features = TextFeatureExtractor.extract(
            raw_text,
            urls=urls,
            invites=invites,
            has_shortener=has_shortener,
            mention_count=mention_count,
            role_mention_count=role_mention_count,
            channel_mention_count=channel_mention_count,
            duplicate_text_score=recent_activity["duplicate_text_score"],
            recent_user_messages_10s=int(recent_activity["recent_user_messages_10s"]),
            recent_user_messages_60s=int(recent_activity["recent_user_messages_60s"]),
            recent_user_messages_10m=int(recent_activity["recent_user_messages_10m"]),
            repeated_messages_10m=int(recent_activity["repeated_messages_10m"]),
            message_interval_seconds=recent_activity["message_interval_seconds"],
        )

        context = MessageContext(
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
        self._validate_payload_settings(payload.metadata)
        rule_matches = self._rule_engine.evaluate(context)

        # Preprocessing emits explainable signals only; final actions stay in Decision Engine.
        context = replace(
            context,
            metadata={
                **context.metadata,
                "preprocessing_rule_matches": [match.to_dict() for match in rule_matches],
                "preprocessing_labels": sorted(
                    {
                        label.value
                        for match in rule_matches
                        for label in match.labels
                    },
                ),
            },
        )
        logger.info(
            "Text preprocessing finished message_id=%s language=%s rule_matches=%s",
            context.message_id,
            context.language,
            len(rule_matches),
        )
        return context

    def _resolve_mention_counts(self, payload: MessagePreprocessInputSchema) -> tuple[int, int, int]:
        raw_text = payload.raw_text or ""
        user_mentions = max(payload.mention_count, MentionExtractor.count_user_mentions(raw_text))
        role_mentions = max(payload.role_mention_count, MentionExtractor.count_role_mentions(raw_text))
        channel_mentions = max(payload.channel_mention_count, MentionExtractor.count_channel_mentions(raw_text))

        logger.info(
            "Mention counts resolved message_id=%s user=%s role=%s channel=%s",
            payload.message_id,
            user_mentions,
            role_mentions,
            channel_mentions,
        )
        return user_mentions, role_mentions, channel_mentions

    def _build_recent_activity(
        self,
        payload: MessagePreprocessInputSchema,
        normalized_text: str,
    ) -> dict[str, int | float | None]:
        timestamps = tuple(self._normalize_datetime(value) for value in payload.recent_message_timestamps)
        repeated_messages_10m = self._count_repeated_messages(payload, normalized_text, timestamps)
        duplicate_text_score = repeated_messages_10m / len(payload.recent_messages) if payload.recent_messages else 0.0

        activity = {
            "duplicate_text_score": duplicate_text_score,
            "recent_user_messages_10s": self._count_recent_messages(payload.created_at, timestamps, 10),
            "recent_user_messages_60s": self._count_recent_messages(payload.created_at, timestamps, 60),
            "recent_user_messages_10m": self._count_recent_messages(payload.created_at, timestamps, 600),
            "repeated_messages_10m": repeated_messages_10m,
            "message_interval_seconds": self._calculate_message_interval(payload.created_at, timestamps),
        }
        logger.info("Recent activity built message_id=%s activity=%s", payload.message_id, activity)
        return activity

    def _count_repeated_messages(
        self,
        payload: MessagePreprocessInputSchema,
        normalized_text: str,
        timestamps: tuple[datetime, ...],
    ) -> int:
        repeated_messages = 0

        for index, recent_message in enumerate(payload.recent_messages):
            if timestamps and index < len(timestamps):
                age_seconds = (self._normalize_datetime(payload.created_at) - timestamps[index]).total_seconds()

                if age_seconds < 0 or age_seconds > 600:
                    continue

            if TextNormalizer.normalize(recent_message) == normalized_text:
                repeated_messages += 1

        return repeated_messages

    def _count_recent_messages(
        self,
        current_at: datetime,
        timestamps: tuple[datetime, ...],
        window_seconds: int,
    ) -> int:
        normalized_current_at = self._normalize_datetime(current_at)
        return sum(
            0 <= (normalized_current_at - timestamp).total_seconds() <= window_seconds
            for timestamp in timestamps
        )

    def _calculate_message_interval(
        self,
        current_at: datetime,
        timestamps: tuple[datetime, ...],
    ) -> float | None:
        normalized_current_at = self._normalize_datetime(current_at)
        intervals = [
            (normalized_current_at - timestamp).total_seconds()
            for timestamp in timestamps
            if (normalized_current_at - timestamp).total_seconds() >= 0
        ]

        if not intervals:
            return None

        return round(min(intervals), 3)

    def _validate_payload_settings(self, metadata: Mapping[str, object]) -> None:
        if "preprocessing_rule_settings" in metadata:
            logger.warning(
                "Ignoring preprocessing_rule_settings from payload metadata; use YAML or injected module settings",
            )


    @staticmethod
    def _domain_matches_any(domain: str, patterns: frozenset[str]) -> bool:
        normalized_domain = domain.lower().removeprefix("www.")
        return any(
            normalized_domain == pattern or normalized_domain.endswith(f".{pattern}")
            for pattern in patterns
        )

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

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
