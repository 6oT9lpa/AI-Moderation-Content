from __future__ import annotations

import re
from typing import Any

from src.domain.message_context import MessageContext
from src.domain.moderation.moderation_label import ModerationLabel
from src.infrastructure.logging import get_logger
from src.modules.preprocessing.rules.preprocessing_rule_policy import PreprocessingRulePolicy
from src.modules.preprocessing.rules.preprocessing_rule_result import PreprocessingRuleResult
from src.modules.preprocessing.rules.preprocessing_rule_settings import PreprocessingRuleSettings

logger = get_logger(__name__)


class PreprocessingRuleEngine:
    DISCORD_INVITE_DOMAINS = (
        "discord.gg",
        "discord.com",
        "discordapp.com",
        "canary.discord.com",
        "ptb.discord.com",
    )

    def __init__(self, settings: PreprocessingRuleSettings | None = None) -> None:
        self._settings = settings or PreprocessingRuleSettings()
        logger.info("Preprocessing rule engine initialized settings=%s", self._settings)

    def evaluate(self, context: MessageContext) -> tuple[PreprocessingRuleResult, ...]:
        features = context.features

        if features is None:
            logger.warning("Preprocessing rule evaluation skipped reason=missing_features")
            return ()

        results: list[PreprocessingRuleResult] = []
        results.extend(self._evaluate_blacklist_words(context))
        semantic_results = self._evaluate_semantic(context)
        results.extend(semantic_results)
        results.extend(self._evaluate_flood(context))
        results.extend(self._evaluate_spam(context, semantic_results))
        results.extend(self._evaluate_invite(context))
        results.extend(self._evaluate_links(context))
        results.extend(self._evaluate_evasion(context))

        logger.info(
            "Preprocessing rule evaluation finished message_id=%s matches=%s labels=%s",
            context.message_id,
            len(results),
            sorted({label.value for result in results for label in result.labels}),
        )
        return tuple(results)

    def _evaluate_blacklist_words(self, context: MessageContext) -> list[PreprocessingRuleResult]:
        blacklist_policy = self._settings.blacklist_words

        if not blacklist_policy.detected.enabled or not blacklist_policy.words:
            return []

        matched_words = tuple(
            word
            for word in blacklist_policy.words
            if self._contains_blacklist_word(context.normalized_text, word)
        )

        if not matched_words:
            return []

        return [
            self._build_result(
                "preprocessing.blacklist_words.detected",
                blacklist_policy.detected,
                {
                    "matched_words": matched_words,
                },
            ),
        ]

    def _evaluate_semantic(self, context: MessageContext) -> list[PreprocessingRuleResult]:
        semantic = self._settings.semantic
        matches: list[PreprocessingRuleResult] = []

        hate_keywords = self._matching_keywords(context.normalized_text, semantic.hate_keywords)
        if semantic.hate.enabled and hate_keywords:
            matches.append(
                self._build_result(
                    "preprocessing.semantic.hate",
                    semantic.hate,
                    {"matched_keyword_count": len(hate_keywords), "input_redacted": True},
                ),
            )

        nsfw_keywords = self._matching_keywords(context.normalized_text, semantic.nsfw_keywords)
        if semantic.nsfw.enabled and nsfw_keywords:
            matches.append(
                self._build_result(
                    "preprocessing.semantic.nsfw",
                    semantic.nsfw,
                    {"matched_keyword_count": len(nsfw_keywords), "input_redacted": True},
                ),
            )

        profanity_terms = self._matching_profanity_terms(context.normalized_text, semantic.profanity_terms)
        if semantic.profanity.enabled and profanity_terms:
            matches.append(
                self._build_result(
                    "preprocessing.semantic.profanity",
                    semantic.profanity,
                    {"matched_term_count": len(profanity_terms), "input_redacted": True},
                ),
            )

        politics_keywords = self._matching_keywords(context.normalized_text, semantic.politics_keywords)
        if semantic.politics.enabled and politics_keywords:
            matches.append(
                self._build_result(
                    "preprocessing.semantic.politics",
                    semantic.politics,
                    {"matched_keyword_count": len(politics_keywords), "input_redacted": True},
                ),
            )

        return matches

    def _evaluate_flood(self, context: MessageContext) -> list[PreprocessingRuleResult]:
        features = context.features
        assert features is not None

        matches: list[PreprocessingRuleResult] = []
        flood = self._settings.flood

        if self._is_threshold_reached(flood.messages_10s, features.recent_user_messages_10s):
            matches.append(
                self._build_result(
                    "preprocessing.flood.messages_10s",
                    flood.messages_10s,
                    {"recent_user_messages_10s": features.recent_user_messages_10s},
                ),
            )

        if self._is_threshold_reached(flood.messages_60s, features.recent_user_messages_60s):
            matches.append(
                self._build_result(
                    "preprocessing.flood.messages_60s",
                    flood.messages_60s,
                    {"recent_user_messages_60s": features.recent_user_messages_60s},
                ),
            )

        if self._is_threshold_reached(flood.repeated_messages_10m, features.repeated_messages_10m):
            matches.append(
                self._build_result(
                    "preprocessing.flood.repeated_messages_10m",
                    flood.repeated_messages_10m,
                    {"repeated_messages_10m": features.repeated_messages_10m},
                ),
            )

        return matches

    def _evaluate_spam(
        self,
        context: MessageContext,
        semantic_results: list[PreprocessingRuleResult],
    ) -> list[PreprocessingRuleResult]:
        features = context.features
        assert features is not None

        matches: list[PreprocessingRuleResult] = []
        spam = self._settings.spam

        if self._is_threshold_reached(spam.mass_mentions, features.mention_count):
            matches.append(
                self._build_result(
                    "preprocessing.spam.mass_mentions",
                    spam.mass_mentions,
                    {"mention_count": features.mention_count},
                ),
            )

        semantic_labels = {label for result in semantic_results for label in result.labels}
        targeted_labels = {ModerationLabel.PROFANITY, ModerationLabel.HATE, ModerationLabel.THREAT}
        if (
            self._is_threshold_reached(spam.targeted_mass_mentions, features.mention_count)
            and semantic_labels.intersection(targeted_labels)
        ):
            matches.append(
                self._build_result(
                    "preprocessing.targeted.mass_mentions",
                    spam.targeted_mass_mentions,
                    {
                        "mention_count": features.mention_count,
                        "semantic_labels": sorted(label.value for label in semantic_labels),
                    },
                ),
            )

        if self._is_threshold_reached(spam.caps, features.uppercase_ratio, text_length=features.text_length):
            matches.append(
                self._build_result(
                    "preprocessing.spam.caps",
                    spam.caps,
                    {"uppercase_ratio": features.uppercase_ratio, "text_length": features.text_length},
                ),
            )

        if self._is_threshold_reached(spam.emoji, features.emoji_ratio, text_length=features.text_length):
            matches.append(
                self._build_result(
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
                self._build_result(
                    "preprocessing.spam.repeated_chars",
                    spam.repeated_chars,
                    {"repeated_char_score": features.repeated_char_score, "text_length": features.text_length},
                ),
            )

        return matches

    def _evaluate_invite(self, context: MessageContext) -> list[PreprocessingRuleResult]:
        invite_policy = self._settings.invite

        if not invite_policy.detected.enabled or not context.invites:
            return []

        blocked_invites = tuple(
            invite for invite in context.invites if invite.lower() not in invite_policy.allowed_invite_codes
        )

        if not blocked_invites:
            return []

        return [
            self._build_result(
                "preprocessing.invite.detected",
                invite_policy.detected,
                {
                    "invites": context.invites,
                    "blocked_invites": blocked_invites,
                    "allowed_invite_codes": invite_policy.allowed_invite_codes,
                },
            ),
        ]

    def _evaluate_links(self, context: MessageContext) -> list[PreprocessingRuleResult]:
        features = context.features
        assert features is not None

        matches: list[PreprocessingRuleResult] = []
        link_policy = self._settings.links
        domains = self._filter_policy_allowed_invite_domains(context)
        untrusted_domains = self._filter_untrusted_domains(domains, link_policy.allowed_domains)

        if link_policy.detect_any_url.enabled and features.has_url and untrusted_domains:
            matches.append(
                self._build_result(
                    "preprocessing.url.detected",
                    link_policy.detect_any_url,
                    {
                        "domains": context.domains,
                        "untrusted_domains": untrusted_domains,
                        "allowed_domains": link_policy.allowed_domains,
                    },
                ),
            )

        shortener_domains = tuple(
            domain
            for domain in domains
            if self._domain_matches_any(domain, link_policy.shortener_domains)
            and not self._domain_matches_any(domain, link_policy.allowed_domains)
        )

        if link_policy.shortener.enabled and features.has_shortener and shortener_domains:
            matches.append(
                self._build_result(
                    "preprocessing.url.shortener",
                    link_policy.shortener,
                    {
                        "domains": context.domains,
                        "shortener_domains": shortener_domains,
                        "allowed_domains": link_policy.allowed_domains,
                    },
                ),
            )

        return matches

    def _filter_policy_allowed_invite_domains(self, context: MessageContext) -> tuple[str, ...]:
        if not context.invites:
            return context.domains

        invite_policy = self._settings.invite
        allowed_codes = set(invite_policy.allowed_invite_codes)
        invite_allowed_by_policy = not invite_policy.detected.enabled or all(
            invite.lower() in allowed_codes for invite in context.invites
        )

        if not invite_allowed_by_policy:
            return context.domains

        return tuple(
            domain
            for domain in context.domains
            if not self._domain_matches_any(domain, self.DISCORD_INVITE_DOMAINS)
        )

    def _evaluate_evasion(self, context: MessageContext) -> list[PreprocessingRuleResult]:
        features = context.features
        assert features is not None

        evasion = self._settings.evasion.unicode

        if not evasion.enabled or not (features.has_mixed_scripts or features.has_suspicious_unicode):
            return []

        return [
            self._build_result(
                "preprocessing.evasion.unicode",
                evasion,
                {
                    "has_mixed_scripts": features.has_mixed_scripts,
                    "has_suspicious_unicode": features.has_suspicious_unicode,
                },
            ),
        ]

    def _build_result(
        self,
        rule_id: str,
        policy: PreprocessingRulePolicy,
        evidence: dict[str, Any],
    ) -> PreprocessingRuleResult:
        return PreprocessingRuleResult(
            rule_id=rule_id,
            labels=policy.labels,
            severity=policy.severity,
            confidence=policy.confidence,
            reason=policy.reason,
            risk_weight=policy.risk_weight,
            evidence=evidence,
        )

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

    def _filter_untrusted_domains(
        self,
        domains: tuple[str, ...],
        allowed_domains: tuple[str, ...],
    ) -> tuple[str, ...]:
        return tuple(domain for domain in domains if not self._domain_matches_any(domain, allowed_domains))

    def _domain_matches_any(self, domain: str, patterns: tuple[str, ...]) -> bool:
        normalized_domain = domain.lower().removeprefix("www.")
        return any(
            normalized_domain == pattern or normalized_domain.endswith(f".{pattern}")
            for pattern in patterns
        )

    def _contains_blacklist_word(self, text: str, word: str) -> bool:
        if not word:
            return False

        pattern = rf"(?<![\w]){re.escape(word)}(?![\w])"
        return re.search(pattern, text.casefold(), flags=re.UNICODE) is not None

    def _matching_keywords(self, text: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
        normalized_text = text.casefold()
        return tuple(
            keyword
            for keyword in keywords
            if self._contains_semantic_keyword(normalized_text, keyword)
        )

    def _contains_semantic_keyword(self, text: str, keyword: str) -> bool:
        if not keyword:
            return False

        if "*" in keyword:
            pattern = re.escape(keyword).replace(r"\*", r"[\w-]*")
        else:
            pattern = re.escape(keyword)

        if " " not in keyword:
            pattern = rf"(?<![\w]){pattern}(?![\w])"
        return re.search(pattern, text, flags=re.UNICODE) is not None

    def _matching_profanity_terms(self, text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
        """Find Russian profanity by stems and typo-tolerant character chunks.

        The matcher intentionally emits only a low-risk PROFANITY signal. A targeted
        insult remains the responsibility of the contextual classifier's TOXIC label.
        """
        tokens = tuple(re.findall(r"[\w-]+", text.casefold(), flags=re.UNICODE))
        return tuple(
            term
            for term in terms
            if any(self._token_matches_profanity(token, term) for token in tokens)
        )

    @staticmethod
    def _token_matches_profanity(token: str, term: str) -> bool:
        normalized_term = term.casefold()
        if len(normalized_term) < 3:
            return False
        if normalized_term in token:
            return True

        # Character trigrams preserve a useful part of a word when one letter is
        # substituted ("бездарь" -> "бездард") or a suffix is added.
        if len(token) < 5 or len(normalized_term) < 5:
            return False
        token_chunks = {token[index:index + 3] for index in range(len(token) - 2)}
        term_chunks = {normalized_term[index:index + 3] for index in range(len(normalized_term) - 2)}
        overlap = len(token_chunks & term_chunks) / len(term_chunks)
        return overlap >= 0.8
