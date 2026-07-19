from __future__ import annotations

from collections.abc import Iterable

from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.signal_source import SignalSource
from src.infrastructure.logging import get_logger
from src.modules.preprocessing.rules.preprocessing_rule_policy import PreprocessingRulePolicy
from src.modules.preprocessing.rules.preprocessing_rule_settings import PreprocessingRuleSettings
from src.contracts.rules.moderation_rule_policy import ModerationRulePolicy

logger = get_logger(__name__)


class PreprocessingModerationPolicyAdapter:
    def adapt(
        self,
        settings: PreprocessingRuleSettings,
        moderation_policy: ModerationRulePolicy,
    ) -> PreprocessingRuleSettings:
        logger.info(
            "Adapting preprocessing policy to moderation policy policy_id=%s version=%s",
            moderation_policy.policy_id,
            moderation_policy.version,
        )

        errors: list[str] = []
        self._validate_preprocessing_source(moderation_policy, errors)

        for rule_path, rule_policy in self._iter_rule_policies(settings):
            if not rule_policy.enabled:
                logger.debug("Skipping disabled preprocessing rule policy rule_path=%s", rule_path)
                continue

            self._validate_rule_policy(rule_path, rule_policy, moderation_policy, errors)

        if errors:
            logger.error(
                "Preprocessing policy is incompatible with moderation policy policy_id=%s errors=%s",
                moderation_policy.policy_id,
                errors,
            )
            raise ValueError("Preprocessing policy is incompatible with moderation policy: " + "; ".join(errors))

        logger.info(
            "Preprocessing policy adapted to moderation policy policy_id=%s version=%s",
            moderation_policy.policy_id,
            moderation_policy.version,
        )
        return settings

    def _validate_preprocessing_source(
        self,
        moderation_policy: ModerationRulePolicy,
        errors: list[str],
    ) -> None:
        source_weight = getattr(moderation_policy.source_weights, SignalSource.PREPROCESSING.value)

        if source_weight <= 0:
            errors.append("source_weights.PREPROCESSING must be greater than 0")

    def _validate_rule_policy(
        self,
        rule_path: str,
        rule_policy: PreprocessingRulePolicy,
        moderation_policy: ModerationRulePolicy,
        errors: list[str],
    ) -> None:
        if rule_policy.severity not in moderation_policy.severity_multipliers:
            errors.append(f"{rule_path}.severity={rule_policy.severity} is missing in severity_multipliers")

        if rule_policy.risk_weight > moderation_policy.risk_score.max:
            errors.append(
                f"{rule_path}.risk_weight={rule_policy.risk_weight} exceeds "
                f"risk_score.max={moderation_policy.risk_score.max}",
            )

        for label in rule_policy.labels:
            self._validate_label(rule_path, label, rule_policy, moderation_policy, errors)

    def _validate_label(
        self,
        rule_path: str,
        label: ModerationLabel,
        rule_policy: PreprocessingRulePolicy,
        moderation_policy: ModerationRulePolicy,
        errors: list[str],
    ) -> None:
        label_weight = getattr(moderation_policy.label_weights, label.value)
        min_confidence = self._resolve_min_confidence(label, moderation_policy)

        if label not in moderation_policy.primary_label_priority:
            errors.append(f"{rule_path}.labels contains {label.value}, but it is missing in primary_label_priority")

        if rule_policy.confidence < min_confidence:
            errors.append(
                f"{rule_path}.confidence={rule_policy.confidence} is below moderation threshold "
                f"{min_confidence} for label={label.value} source=PREPROCESSING",
            )

        if label_weight <= 0 and label != ModerationLabel.SAFE:
            errors.append(f"{rule_path}.labels contains {label.value}, but label_weights.{label.value} is not positive")

    def _resolve_min_confidence(
        self,
        label: ModerationLabel,
        moderation_policy: ModerationRulePolicy,
    ) -> float:
        thresholds = moderation_policy.confidence_thresholds
        selected_threshold = thresholds.default_min_confidence
        source_threshold = thresholds.per_source_min_confidence.get(SignalSource.PREPROCESSING.value)
        label_threshold = thresholds.per_label_min_confidence.get(label.value)

        if source_threshold is not None:
            selected_threshold = source_threshold

        if label_threshold is not None:
            selected_threshold = label_threshold

        return selected_threshold

    def _iter_rule_policies(
        self,
        settings: PreprocessingRuleSettings,
    ) -> Iterable[tuple[str, PreprocessingRulePolicy]]:
        yield "links.detect_any_url", settings.links.detect_any_url
        yield "links.shortener", settings.links.shortener
        yield "flood.messages_10s", settings.flood.messages_10s
        yield "flood.messages_60s", settings.flood.messages_60s
        yield "flood.repeated_messages_10m", settings.flood.repeated_messages_10m
        yield "spam.mass_mentions", settings.spam.mass_mentions
        yield "spam.caps", settings.spam.caps
        yield "spam.emoji", settings.spam.emoji
        yield "spam.repeated_chars", settings.spam.repeated_chars
        yield "invite.detected", settings.invite.detected
        yield "evasion.unicode", settings.evasion.unicode
        yield "semantic.hate", settings.semantic.hate
        yield "semantic.nsfw", settings.semantic.nsfw
        yield "semantic.politics", settings.semantic.politics
        yield "russian_profanity.obscene", settings.russian_profanity.obscene
        yield "russian_profanity.literary", settings.russian_profanity.literary
