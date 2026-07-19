from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.modules.preprocessing.detectors.mention_extractor import MentionExtractor
from src.modules.preprocessing.detectors.russian_profanity_detector import RussianProfanityDetector
from src.modules.preprocessing.rules.preprocessing_rule_config_loader import PreprocessingRuleConfigLoader
from src.modules.preprocessing.rules.preprocessing_rule_policy import PreprocessingRulePolicy
from src.modules.preprocessing.rules.preprocessing_rule_settings import PreprocessingRuleSettings
from src.modules.preprocessing.text_feature_extractor import TextFeatureExtractor
from src.modules.preprocessing.text_normalizer import TextNormalizer
from src.modules.preprocessing.url_extractor import UrlExtractor


class PreprocessingFixtureExpectationBuilder:
    def __init__(self, config_path: str = "configs/rules/preprocessing_rules.yaml") -> None:
        self._settings = PreprocessingRuleConfigLoader().load(config_path)
        self._shortener_domains = frozenset(self._settings.links.shortener_domains)
        self._russian_profanity_detector = RussianProfanityDetector(self._settings.russian_profanity)
        self._config_path = config_path

    def build(self, case: dict[str, Any]) -> dict[str, Any]:
        payload = MessagePreprocessInputSchema(**case["input"])
        raw_text = payload.raw_text or ""
        normalized_text = TextNormalizer.normalize(raw_text)
        urls = UrlExtractor.extract_urls(raw_text)
        domains = UrlExtractor.extract_domains(urls)
        invites = UrlExtractor.extract_discord_invites(raw_text)
        timestamps = tuple(self._normalize_datetime(value) for value in payload.recent_message_timestamps)
        repeated_messages_10m = self._count_repeated_messages(payload, normalized_text, timestamps)
        mention_count = max(payload.mention_count, MentionExtractor.count_user_mentions(raw_text))
        features = TextFeatureExtractor.extract(
            raw_text,
            urls=urls,
            invites=invites,
            has_shortener=any(self._domain_matches_any(domain, self._shortener_domains) for domain in domains),
            mention_count=mention_count,
            role_mention_count=max(payload.role_mention_count, MentionExtractor.count_role_mentions(raw_text)),
            channel_mention_count=max(payload.channel_mention_count, MentionExtractor.count_channel_mentions(raw_text)),
            duplicate_text_score=repeated_messages_10m / len(payload.recent_messages)
            if payload.recent_messages
            else 0.0,
            recent_user_messages_10s=self._count_recent_messages(payload.created_at, timestamps, 10),
            recent_user_messages_60s=self._count_recent_messages(payload.created_at, timestamps, 60),
            recent_user_messages_10m=self._count_recent_messages(payload.created_at, timestamps, 600),
            repeated_messages_10m=repeated_messages_10m,
            message_interval_seconds=self._calculate_message_interval(payload.created_at, timestamps),
        )

        rule_matches = self._build_rule_matches(features, invites, domains, normalized_text)
        detected_labels = sorted(
            {
                label
                for match in rule_matches
                for label in match["labels"]
            },
        )
        confidences = [
            match["confidence"]
            for match in rule_matches
            if match.get("confidence") is not None
        ]

        return {
            "config_source": self._config_path,
            "settings": self._settings.model_dump(mode="json"),
            "preprocessing_verdict": "SAFE" if not detected_labels else "SIGNAL",
            "detected_labels": detected_labels,
            "rule_matches": rule_matches,
            "confidence": max(confidences) if confidences else None,
            "model_confidence": None,
        }

    def _build_rule_matches(
        self,
        features,
        invites: tuple[str, ...],
        domains: tuple[str, ...],
        normalized_text: str,
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []

        flood = self._settings.flood
        spam = self._settings.spam
        invite = self._settings.invite
        links = self._settings.links
        evasion = self._settings.evasion
        semantic = self._settings.semantic
        russian_profanity = self._settings.russian_profanity

        russian_matches = self._russian_profanity_detector.find_matches(normalized_text)
        for category, policy in (
            ("obscene", russian_profanity.obscene),
            ("literary", russian_profanity.literary),
        ):
            matched_words = russian_matches.get(category, ())
            if policy.enabled and matched_words:
                matches.append(
                    self._match(
                        f"preprocessing.russian_profanity.{category}",
                        policy,
                        {"matched_word_count": len(matched_words), "input_redacted": True},
                    ),
                )

        hate_keywords = self._matching_keywords(normalized_text, semantic.hate_keywords)
        if semantic.hate.enabled and hate_keywords:
            matches.append(self._match("preprocessing.semantic.hate", semantic.hate, {"matched_keyword_count": len(hate_keywords), "input_redacted": True}))

        nsfw_keywords = self._matching_keywords(normalized_text, semantic.nsfw_keywords)
        if semantic.nsfw.enabled and nsfw_keywords:
            matches.append(self._match("preprocessing.semantic.nsfw", semantic.nsfw, {"matched_keyword_count": len(nsfw_keywords), "input_redacted": True}))

        politics_keywords = self._matching_keywords(normalized_text, semantic.politics_keywords)
        if semantic.politics.enabled and politics_keywords:
            matches.append(self._match("preprocessing.semantic.politics", semantic.politics, {"matched_keyword_count": len(politics_keywords), "input_redacted": True}))

        if self._is_threshold_reached(flood.messages_10s, features.recent_user_messages_10s):
            matches.append(
                self._match(
                    "preprocessing.flood.messages_10s",
                    flood.messages_10s,
                    {"recent_user_messages_10s": features.recent_user_messages_10s},
                ),
            )

        if self._is_threshold_reached(flood.messages_60s, features.recent_user_messages_60s):
            matches.append(
                self._match(
                    "preprocessing.flood.messages_60s",
                    flood.messages_60s,
                    {"recent_user_messages_60s": features.recent_user_messages_60s},
                ),
            )

        if self._is_threshold_reached(flood.repeated_messages_10m, features.repeated_messages_10m):
            matches.append(
                self._match(
                    "preprocessing.flood.repeated_messages_10m",
                    flood.repeated_messages_10m,
                    {"repeated_messages_10m": features.repeated_messages_10m},
                ),
            )

        if self._is_threshold_reached(spam.mass_mentions, features.mention_count):
            matches.append(
                self._match(
                    "preprocessing.spam.mass_mentions",
                    spam.mass_mentions,
                    {"mention_count": features.mention_count},
                ),
            )

        if invite.detected.enabled and invites:
            blocked_invites = tuple(code for code in invites if code.lower() not in invite.allowed_invite_codes)

            if blocked_invites:
                matches.append(
                    self._match(
                        "preprocessing.invite.detected",
                        invite.detected,
                        {
                            "invites": invites,
                            "blocked_invites": blocked_invites,
                            "allowed_invite_codes": invite.allowed_invite_codes,
                        },
                    ),
                )

        untrusted_domains = tuple(
            domain for domain in domains if not self._domain_matches_any(domain, links.allowed_domains)
        )

        if links.detect_any_url.enabled and features.has_url and untrusted_domains:
            matches.append(
                self._match(
                    "preprocessing.url.detected",
                    links.detect_any_url,
                    {
                        "domains": domains,
                        "untrusted_domains": untrusted_domains,
                        "allowed_domains": links.allowed_domains,
                    },
                ),
            )

        shortener_domains = tuple(
            domain
            for domain in domains
            if self._domain_matches_any(domain, links.shortener_domains)
            and not self._domain_matches_any(domain, links.allowed_domains)
        )

        if links.shortener.enabled and features.has_shortener and shortener_domains:
            matches.append(
                self._match(
                    "preprocessing.url.shortener",
                    links.shortener,
                    {
                        "domains": domains,
                        "shortener_domains": shortener_domains,
                        "allowed_domains": links.allowed_domains,
                    },
                ),
            )

        if self._is_threshold_reached(spam.caps, features.uppercase_ratio, text_length=features.text_length):
            matches.append(
                self._match(
                    "preprocessing.spam.caps",
                    spam.caps,
                    {"uppercase_ratio": features.uppercase_ratio, "text_length": features.text_length},
                ),
            )

        if self._is_threshold_reached(spam.emoji, features.emoji_ratio, text_length=features.text_length):
            matches.append(
                self._match(
                    "preprocessing.spam.emoji",
                    spam.emoji,
                    {"emoji_ratio": features.emoji_ratio, "text_length": features.text_length},
                ),
            )

        if self._is_threshold_reached(
            spam.repeated_chars,
            features.repeated_char_score,
            text_length=features.text_length,
        ):
            matches.append(
                self._match(
                    "preprocessing.spam.repeated_chars",
                    spam.repeated_chars,
                    {"repeated_char_score": features.repeated_char_score, "text_length": features.text_length},
                ),
            )

        if evasion.unicode.enabled and (features.has_mixed_scripts or features.has_suspicious_unicode):
            matches.append(
                self._match(
                    "preprocessing.evasion.unicode",
                    evasion.unicode,
                    {
                        "has_mixed_scripts": features.has_mixed_scripts,
                        "has_suspicious_unicode": features.has_suspicious_unicode,
                    },
                ),
            )

        return matches

    def _match(
        self,
        rule_id: str,
        policy: PreprocessingRulePolicy,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "rule_id": rule_id,
            "labels": [label.value for label in policy.labels],
            "severity": policy.severity,
            "confidence": policy.confidence,
            "reason": policy.reason,
            "risk_weight": policy.risk_weight,
            "evidence": evidence,
        }

    def _is_threshold_reached(
        self,
        policy: PreprocessingRulePolicy,
        value: float | int,
        *,
        text_length: int | None = None,
    ) -> bool:
        if not policy.enabled or policy.threshold is None:
            return False

        if text_length is not None and text_length < policy.minimum_text_length:
            return False

        return value >= policy.threshold

    def _domain_matches_any(self, domain: str, patterns: tuple[str, ...] | frozenset[str]) -> bool:
        normalized_domain = domain.lower().removeprefix("www.")
        return any(
            normalized_domain == pattern or normalized_domain.endswith(f".{pattern}")
            for pattern in patterns
        )

    def _matching_keywords(self, text: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(keyword for keyword in keywords if self._contains_semantic_keyword(text, keyword))

    def _contains_semantic_keyword(self, text: str, keyword: str) -> bool:
        import re

        pattern = re.escape(keyword).replace(r"\*", r"[\w-]*")
        if " " not in keyword:
            pattern = rf"(?<![\w]){pattern}(?![\w])"
        return re.search(pattern, text, flags=re.UNICODE) is not None

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

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)
