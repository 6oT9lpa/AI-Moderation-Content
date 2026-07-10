from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.infrastructure.logging import get_logger
from src.modules.preprocessing.rules.preprocessing_rule_config_loader import PreprocessingRuleConfigLoader
from src.modules.preprocessing.rules.preprocessing_rule_settings import PreprocessingRuleSettings
from src.modules.preprocessing.text_preprocessor import TextPreprocessor

logger = get_logger("tests.preprocessing")


def test_preprocessing_rule_settings_rejects_invalid_confidence(structured_test_logger) -> None:
    invalid_settings = {
        "links": {
            "detect_any_url": {
                "confidence": 1.5,
            },
        },
    }
    structured_test_logger(
        "input",
        {
            "invalid_settings": invalid_settings,
            "expected_error": "confidence must be between 0.0 and 1.0",
        },
    )

    with pytest.raises(ValidationError) as exc_info:
        PreprocessingRuleSettings.from_mapping(invalid_settings)

    structured_test_logger("output", {"errors": exc_info.value.errors()})
    assert exc_info.value.errors()[0]["loc"] == ("links", "detect_any_url", "confidence")


def test_preprocessing_rule_settings_rejects_unknown_policy_key(structured_test_logger) -> None:
    invalid_settings = {
        "spam": {
            "mass_mentions": {
                "confidense": 0.8,
            },
        },
    }
    structured_test_logger(
        "input",
        {
            "invalid_settings": invalid_settings,
            "expected_error": "extra key is forbidden",
        },
    )

    with pytest.raises(ValidationError) as exc_info:
        PreprocessingRuleSettings.from_mapping(invalid_settings)

    structured_test_logger("output", {"errors": exc_info.value.errors()})
    assert exc_info.value.errors()[0]["loc"] == ("spam", "mass_mentions", "confidense")


def test_preprocessing_rule_settings_maps_legacy_flat_thresholds(structured_test_logger) -> None:
    settings = PreprocessingRuleSettings.from_mapping(
        {
            "detect_any_url": False,
            "max_messages_10s": 9,
            "mass_mentions_threshold": 7,
        },
    )
    structured_test_logger(
        "output",
        {
            "detect_any_url": settings.detect_any_url,
            "flood_messages_10s_threshold": settings.flood.messages_10s.threshold,
            "spam_mass_mentions_threshold": settings.spam.mass_mentions.threshold,
        },
    )

    assert settings.detect_any_url is False
    assert settings.flood.messages_10s.threshold == 9
    assert settings.spam.mass_mentions.threshold == 7


def test_preprocessing_rule_config_loader_adapts_to_moderation_policy(structured_test_logger) -> None:
    settings = PreprocessingRuleConfigLoader().load("configs/rules/preprocessing_rules.yaml")

    structured_test_logger(
        "output",
        {
            "policy_source": "configs/rules/moderation_rule_policy.yaml",
            "url_confidence": settings.links.detect_any_url.confidence,
            "invite_confidence": settings.invite.detected.confidence,
            "flood_confidence": settings.flood.messages_10s.confidence,
        },
    )

    assert settings.links.detect_any_url.confidence >= 0.3
    assert settings.invite.detected.confidence >= 0.3
    assert settings.flood.messages_10s.confidence >= 0.3


def test_preprocessing_rule_config_loader_rejects_rules_below_moderation_confidence(
    tmp_path,
    structured_test_logger,
) -> None:
    config_path = tmp_path / "preprocessing_rules.yaml"
    config_path.write_text(
        """
preprocessing:
  links:
    detect_any_url:
      enabled: true
      labels: [URL]
      severity: 1
      confidence: 0.1
      risk_weight: 10
      reason: url_detected
""",
        encoding="utf-8",
    )

    structured_test_logger(
        "input",
        {
            "config_path": str(config_path),
            "expected_error": "confidence is below moderation threshold",
            "moderation_policy_source": "configs/rules/moderation_rule_policy.yaml",
        },
    )

    with pytest.raises(ValueError, match="below moderation threshold") as exc_info:
        PreprocessingRuleConfigLoader().load(config_path)

    structured_test_logger("output", {"error": str(exc_info.value)})


def _log_preprocessing_context(structured_test_logger, context, *, expected: dict[str, Any] | None = None) -> None:
    rule_matches = context.metadata.get("preprocessing_rule_matches", [])
    detected_labels = context.metadata.get("preprocessing_labels", [])
    confidences = [
        match.get("confidence")
        for match in rule_matches
        if isinstance(match, dict) and match.get("confidence") is not None
    ]

    structured_test_logger(
        "output",
        {
            "message_id": context.message_id,
            "normalized_text": context.normalized_text,
            "language": context.language,
            "text_hash": context.text_hash,
            "urls": context.urls,
            "domains": context.domains,
            "invites": context.invites,
            "has_url": context.has_url,
            "has_invite": context.has_invite,
            "has_shortener": context.has_shortener,
            "features": context.features.to_dict() if context.features else None,
        },
    )
    structured_test_logger(
        "detection",
        {
            "expected": expected or {},
            "preprocessing_verdict": "SAFE" if not detected_labels else "SIGNAL",
            "detected_labels": detected_labels,
            "rule_matches": rule_matches,
            "confidence": max(confidences) if confidences else None,
            "model_confidence": None,
        },
    )


@pytest.mark.asyncio
async def test_text_preprocessor_builds_message_context(structured_test_logger) -> None:
    created_at = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
    author_created_at = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    member_joined_at = datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc)

    payload = MessagePreprocessInputSchema(
        platform="discord",
        guild_id="guild-1",
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="HELLO   привет https://discord.gg/Test123 😀",
        created_at=created_at,
        author_created_at=author_created_at,
        member_joined_at=member_joined_at,
        mention_count=2,
        role_mention_count=1,
        channel_mention_count=1,
        has_attachments=True,
        attachment_count=2,
        recent_messages=("old message",),
        metadata={"source": "unit_test"},
    )

    context = await TextPreprocessor().process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "normalized_text": "hello привет https://discord.gg/test123 😀",
            "language": "mixed",
            "has_url": True,
            "has_invite": True,
        },
    )

    logger.info(
        "Preprocessor context built message_id=%s language=%s urls=%s domains=%s invites=%s features=%s",
        context.message_id,
        context.language,
        context.urls,
        context.domains,
        context.invites,
        context.features.to_dict() if context.features else None,
    )

    assert context.platform == "discord"
    assert context.guild_id == "guild-1"
    assert context.channel_id == "channel-1"
    assert context.user_id == "user-1"
    assert context.message_id == "message-1"
    assert context.raw_text == payload.raw_text
    assert context.normalized_text == "hello привет https://discord.gg/test123 😀"
    assert len(context.text_hash) == 64
    assert context.language == "mixed"
    assert context.urls == ("https://discord.gg/Test123",)
    assert context.domains == ("discord.gg",)
    assert context.invites == ("test123",)
    assert context.has_url is True
    assert context.has_invite is True
    assert context.has_attachments is True
    assert context.attachment_count == 2
    assert context.account_age_days == 6
    assert context.member_age_days == 4
    assert context.recent_messages == ("old message",)
    assert context.metadata["source"] == "unit_test"
    assert context.metadata["feature_version"] == "text_preprocessor_v1"
    assert "preprocessing_rule_matches" in context.metadata
    assert context.features is not None
    assert context.features.mention_count == 2
    assert context.features.role_mention_count == 1
    assert context.features.channel_mention_count == 1


@pytest.mark.asyncio
async def test_text_preprocessor_applies_yaml_preprocessing_rules(structured_test_logger) -> None:
    created_at = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
    rule_settings = PreprocessingRuleConfigLoader().load("configs/rules/preprocessing_rules.yaml")
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="BUY NOW @one @two @three @four @five bit.ly/scam",
        created_at=created_at,
        recent_messages=("BUY NOW @one @two @three @four @five bit.ly/scam",) * 3,
        recent_message_timestamps=(
            datetime(2026, 7, 7, 11, 59, 58, tzinfo=timezone.utc),
            datetime(2026, 7, 7, 11, 59, 57, tzinfo=timezone.utc),
            datetime(2026, 7, 7, 11, 59, 56, tzinfo=timezone.utc),
            datetime(2026, 7, 7, 11, 59, 55, tzinfo=timezone.utc),
        ),
    )
    expected_flood = (
        len(payload.recent_message_timestamps) >= rule_settings.flood.messages_10s.threshold
        or len(payload.recent_messages) >= rule_settings.flood.repeated_messages_10m.threshold
    )
    expected_labels = ["SPAM", "URL"]

    if expected_flood:
        expected_labels.append("FLOOD")

    context = await TextPreprocessor().process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "config_source": "configs/rules/preprocessing_rules.yaml",
            "flood_messages_10s_threshold": rule_settings.flood.messages_10s.threshold,
            "flood_repeated_messages_10m_threshold": rule_settings.flood.repeated_messages_10m.threshold,
            "spam_mass_mentions_threshold": rule_settings.spam.mass_mentions.threshold,
            "labels": sorted(expected_labels),
            "recent_user_messages_10s": 4,
            "repeated_messages_10m": 3,
        },
    )

    logger.info(
        "Preprocessor primary signals labels=%s matches=%s features=%s",
        context.metadata["preprocessing_labels"],
        context.metadata["preprocessing_rule_matches"],
        context.features.to_dict() if context.features else None,
    )

    assert context.features is not None
    assert context.features.recent_user_messages_10s == 4
    assert context.features.repeated_messages_10m == 3
    assert "SPAM" in context.metadata["preprocessing_labels"]
    assert "URL" in context.metadata["preprocessing_labels"]

    if expected_flood:
        assert "FLOOD" in context.metadata["preprocessing_labels"]
    else:
        assert "FLOOD" not in context.metadata["preprocessing_labels"]


@pytest.mark.asyncio
async def test_text_preprocessor_ignores_payload_preprocessing_rule_settings(structured_test_logger) -> None:
    created_at = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="repeat me",
        created_at=created_at,
        recent_messages=("repeat me",) * 3,
        recent_message_timestamps=(
            datetime(2026, 7, 7, 11, 59, 58, tzinfo=timezone.utc),
            datetime(2026, 7, 7, 11, 59, 57, tzinfo=timezone.utc),
            datetime(2026, 7, 7, 11, 59, 56, tzinfo=timezone.utc),
            datetime(2026, 7, 7, 11, 59, 55, tzinfo=timezone.utc),
        ),
        metadata={
            "preprocessing_rule_settings": {
                "max_messages_10s": 1,
                "max_repeated_messages_10m": 1,
            },
        },
    )
    preprocessor = TextPreprocessor(
        rule_settings=PreprocessingRuleSettings.from_mapping(
            {
                "flood": {
                    "messages_10s": {"threshold": 10},
                    "repeated_messages_10m": {"threshold": 10},
                },
            },
        ),
    )

    context = await preprocessor.process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "metadata_override": "ignored",
            "module_flood_messages_10s_threshold": 10,
            "module_flood_repeated_messages_10m_threshold": 10,
            "labels": [],
        },
    )

    assert "FLOOD" not in context.metadata["preprocessing_labels"]
    assert context.metadata["preprocessing_rule_matches"] == []


@pytest.mark.asyncio
async def test_text_preprocessor_allows_policy_whitelisted_url_domain(structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="watch this https://youtube.com/watch?v=abc123",
    )

    context = await TextPreprocessor().process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "allowed_domains": ["youtube.com", "youtu.be", "tiktok.com", "vm.tiktok.com"],
            "has_url": True,
            "labels": [],
        },
    )

    assert context.has_url is True
    assert context.domains == ("youtube.com",)
    assert "URL" not in context.metadata["preprocessing_labels"]
    assert context.metadata["preprocessing_rule_matches"] == []


@pytest.mark.asyncio
async def test_text_preprocessor_allows_policy_whitelisted_invite_code(structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="join https://discord.gg/Qwert",
    )
    preprocessor = TextPreprocessor(
        rule_settings=PreprocessingRuleSettings.from_mapping(
            {
                "links": {
                    "allowed_domains": [],
                },
                "invite": {
                    "allowed_invite_codes": ["qwert"],
                },
            },
        ),
    )

    context = await preprocessor.process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "allowed_invite_codes": ["qwert"],
            "invites": ["qwert"],
            "labels": [],
        },
    )

    assert context.invites == ("qwert",)
    assert "INVITE" not in context.metadata["preprocessing_labels"]
    assert "URL" not in context.metadata["preprocessing_labels"]
    assert context.metadata["preprocessing_rule_matches"] == []


@pytest.mark.asyncio
async def test_text_preprocessor_disabled_invite_policy_does_not_fallback_to_url(structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="join https://discord.gg/Qwert",
    )
    preprocessor = TextPreprocessor(
        rule_settings=PreprocessingRuleSettings.from_mapping(
            {
                "links": {
                    "allowed_domains": [],
                },
                "invite": {
                    "detected": {
                        "enabled": False,
                    },
                },
            },
        ),
    )

    context = await preprocessor.process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "invite_policy_enabled": False,
            "invites": ["qwert"],
            "labels": [],
        },
    )

    assert context.invites == ("qwert",)
    assert context.metadata["preprocessing_rule_matches"] == []


@pytest.mark.asyncio
async def test_text_preprocessor_uses_policy_confidence_and_risk_weight(structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="look https://unknown.example/path",
    )
    preprocessor = TextPreprocessor(
        rule_settings=PreprocessingRuleSettings.from_mapping(
            {
                "links": {
                    "allowed_domains": ["youtube.com"],
                    "detect_any_url": {
                        "confidence": 0.33,
                        "risk_weight": 17,
                        "severity": 2,
                        "reason": "custom_url_policy",
                    },
                },
            },
        ),
    )

    context = await preprocessor.process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "rule_id": "preprocessing.url.detected",
            "confidence": 0.33,
            "risk_weight": 17,
            "severity": 2,
            "reason": "custom_url_policy",
        },
    )
    [match] = context.metadata["preprocessing_rule_matches"]

    assert match["rule_id"] == "preprocessing.url.detected"
    assert match["confidence"] == 0.33
    assert match["risk_weight"] == 17
    assert match["severity"] == 2
    assert match["reason"] == "custom_url_policy"


@pytest.mark.asyncio
async def test_text_preprocessor_url_does_not_mask_caps_spam(structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="OQWEOOQWoooQWOO OQOWEO OQOWEOo https://discord.gg/123123",
    )

    context = await TextPreprocessor().process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "labels": ["INVITE", "SPAM", "URL"],
            "spam_reason": "caps_ratio_threshold_exceeded",
        },
    )

    labels = context.metadata["preprocessing_labels"]
    reasons = {match["reason"] for match in context.metadata["preprocessing_rule_matches"]}

    assert "SPAM" in labels
    assert "INVITE" in labels
    assert "URL" in labels
    assert "caps_ratio_threshold_exceeded" in reasons


@pytest.mark.asyncio
async def test_text_preprocessor_detects_policy_blacklist_word(structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="This message contains forbiddenword.",
    )
    preprocessor = TextPreprocessor(
        rule_settings=PreprocessingRuleSettings.from_mapping(
            {
                "blacklist_words": {
                    "words": ["forbiddenword"],
                },
            },
        ),
    )

    context = await preprocessor.process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "rule_id": "preprocessing.blacklist_words.detected",
            "labels": ["SPAM"],
            "matched_words": ["forbiddenword"],
        },
    )
    [match] = context.metadata["preprocessing_rule_matches"]

    assert match["rule_id"] == "preprocessing.blacklist_words.detected"
    assert match["labels"] == ["SPAM"]
    assert match["evidence"]["matched_words"] == ("forbiddenword",)


@pytest.mark.asyncio
async def test_text_preprocessor_blacklist_word_respects_word_boundaries(structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="This badge should not match.",
    )
    preprocessor = TextPreprocessor(
        rule_settings=PreprocessingRuleSettings.from_mapping(
            {
                "blacklist_words": {
                    "words": ["bad"],
                },
            },
        ),
    )

    context = await preprocessor.process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "labels": [],
            "reason": "badge contains bad as substring only",
        },
    )

    assert context.metadata["preprocessing_rule_matches"] == []


@pytest.mark.asyncio
async def test_text_preprocessor_blacklist_word_can_be_disabled(structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="forbiddenword",
    )
    preprocessor = TextPreprocessor(
        rule_settings=PreprocessingRuleSettings.from_mapping(
            {
                "blacklist_words": {
                    "words": ["forbiddenword"],
                    "detected": {
                        "enabled": False,
                    },
                },
            },
        ),
    )

    context = await preprocessor.process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "blacklist_enabled": False,
            "labels": [],
        },
    )

    assert context.metadata["preprocessing_rule_matches"] == []


@pytest.mark.asyncio
async def test_text_preprocessor_blacklist_word_uses_policy_payload(structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="custombad",
    )
    preprocessor = TextPreprocessor(
        rule_settings=PreprocessingRuleSettings.from_mapping(
            {
                "blacklist_words": {
                    "words": "custombad",
                    "detected": {
                        "labels": ["HATE"],
                        "severity": 5,
                        "confidence": 0.91,
                        "risk_weight": 70,
                        "reason": "custom_blacklist_policy",
                    },
                },
            },
        ),
    )

    context = await preprocessor.process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "labels": ["HATE"],
            "severity": 5,
            "confidence": 0.91,
            "risk_weight": 70,
            "reason": "custom_blacklist_policy",
        },
    )
    [match] = context.metadata["preprocessing_rule_matches"]

    assert match["labels"] == ["HATE"]
    assert match["severity"] == 5
    assert match["confidence"] == 0.91
    assert match["risk_weight"] == 70
    assert match["reason"] == "custom_blacklist_policy"


@pytest.mark.asyncio
async def test_text_preprocessor_detects_semantic_hate_signal(structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="Я ненавижу эту группу людей и хочу чтобы их выгнали.",
    )

    context = await TextPreprocessor().process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "rule_id": "preprocessing.semantic.hate",
            "labels": ["HATE"],
            "input_redacted": True,
        },
    )

    labels = context.metadata["preprocessing_labels"]
    rules = {match["rule_id"] for match in context.metadata["preprocessing_rule_matches"]}
    assert "HATE" in labels
    assert "preprocessing.semantic.hate" in rules


@pytest.mark.asyncio
async def test_text_preprocessor_detects_semantic_nsfw_signal(structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="Пошлый сексуальный контент с описанием интимной сцены.",
    )

    context = await TextPreprocessor().process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "rule_id": "preprocessing.semantic.nsfw",
            "labels": ["NSFW"],
            "input_redacted": True,
        },
    )

    labels = context.metadata["preprocessing_labels"]
    rules = {match["rule_id"] for match in context.metadata["preprocessing_rule_matches"]}
    assert "NSFW" in labels
    assert "preprocessing.semantic.nsfw" in rules


@pytest.mark.asyncio
async def test_text_preprocessor_keeps_repeated_messages_as_flood_not_spam(structured_test_logger) -> None:
    created_at = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="same calm message",
        created_at=created_at,
        recent_messages=("same calm message",) * 3,
        recent_message_timestamps=(
            datetime(2026, 7, 7, 11, 59, 58, tzinfo=timezone.utc),
            datetime(2026, 7, 7, 11, 59, 57, tzinfo=timezone.utc),
            datetime(2026, 7, 7, 11, 59, 56, tzinfo=timezone.utc),
        ),
    )
    preprocessor = TextPreprocessor(
        rule_settings=PreprocessingRuleSettings.from_mapping(
            {
                "flood": {
                    "messages_10s": {"enabled": False},
                    "messages_60s": {"enabled": False},
                    "repeated_messages_10m": {"threshold": 3},
                },
            },
        ),
    )

    context = await preprocessor.process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "rule_id": "preprocessing.flood.repeated_messages_10m",
            "labels": ["FLOOD"],
            "spam_expected": False,
        },
    )

    assert context.metadata["preprocessing_labels"] == ["FLOOD"]
    [match] = context.metadata["preprocessing_rule_matches"]
    assert match["rule_id"] == "preprocessing.flood.repeated_messages_10m"
    assert match["labels"] == ["FLOOD"]


@pytest.mark.asyncio
async def test_text_preprocessor_hash_is_deterministic_for_normalized_text(structured_test_logger) -> None:
    payload_one = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="HELLO    WORLD",
    )
    payload_two = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-2",
        raw_text="hello world",
    )

    preprocessor = TextPreprocessor()
    context_one = await preprocessor.process(payload_one)
    context_two = await preprocessor.process(payload_two)
    structured_test_logger(
        "output",
        {
            "message_one": {
                "message_id": context_one.message_id,
                "normalized_text": context_one.normalized_text,
                "text_hash": context_one.text_hash,
            },
            "message_two": {
                "message_id": context_two.message_id,
                "normalized_text": context_two.normalized_text,
                "text_hash": context_two.text_hash,
            },
            "hashes_match": context_one.text_hash == context_two.text_hash,
        },
    )
    structured_test_logger(
        "detection",
        {
            "expected": {"hashes_match": True},
            "preprocessing_verdict": "SAFE",
            "detected_labels": [],
            "confidence": None,
            "model_confidence": None,
        },
    )

    logger.info(
        "Preprocessor deterministic hash hash_one=%s hash_two=%s normalized_one=%r normalized_two=%r",
        context_one.text_hash,
        context_two.text_hash,
        context_one.normalized_text,
        context_two.normalized_text,
    )

    assert context_one.normalized_text == context_two.normalized_text
    assert context_one.text_hash == context_two.text_hash


@pytest.mark.asyncio
async def test_text_preprocessor_detects_shortener_domain(structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="click bit.ly/scam",
    )

    context = await TextPreprocessor().process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "domains": ("bit.ly",),
            "has_shortener": True,
            "labels": ["URL", "SPAM"],
        },
    )

    logger.info(
        "Preprocessor shortener detection domains=%s has_shortener=%s",
        context.domains,
        context.has_shortener,
    )

    assert context.domains == ("bit.ly",)
    assert context.has_shortener is True
    assert context.features is not None
    assert context.features.has_shortener is True


@pytest.mark.asyncio
async def test_text_preprocessor_detects_unknown_language_for_empty_text(structured_test_logger) -> None:
    payload = MessagePreprocessInputSchema(
        channel_id="channel-1",
        user_id="user-1",
        message_id="message-1",
        raw_text="",
    )

    context = await TextPreprocessor().process(payload)
    _log_preprocessing_context(
        structured_test_logger,
        context,
        expected={
            "normalized_text": "",
            "language": "unknown",
            "has_url": False,
            "has_invite": False,
        },
    )

    logger.info("Preprocessor empty text language=%s features=%s", context.language, context.features)

    assert context.normalized_text == ""
    assert context.language == "unknown"
    assert context.urls == ()
    assert context.domains == ()
    assert context.invites == ()
    assert context.has_url is False
    assert context.has_invite is False
    assert context.features is not None
    assert context.features.text_length == 0
