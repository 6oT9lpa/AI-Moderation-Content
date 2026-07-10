from __future__ import annotations

import re

from src.domain.media.media_attachment_analysis import MediaAttachmentAnalysis
from src.domain.media.media_risk_result import MediaRiskResult
from src.infrastructure.logging import get_logger
from src.modules.media.media_rule_settings import MediaRuleSettings

logger = get_logger(__name__)


class MediaRiskScorer:
    MENTION_RE = re.compile(r"<@!?\d+>|@\w+", re.IGNORECASE)

    def calculate(
        self,
        attachments: tuple[MediaAttachmentAnalysis, ...],
        message_text: str,
        account_age_days: int | None,
        settings: MediaRuleSettings,
    ) -> MediaRiskResult:
        breakdown: list[tuple[str, int]] = []
        if attachments:
            breakdown.append(("has_image", 10))
        if attachments and self._is_short_or_only_mention(message_text, settings.short_text_length):
            breakdown.append(("message_text_short_or_only_mention", 10))
        if any(attachment.known_scam_hash_match for attachment in attachments):
            breakdown.append(("known_scam_image_hash", 70))
        features = [attachment.ocr_features for attachment in attachments]
        if any(feature.has_casino for feature in features):
            breakdown.append(("ocr_has_casino", 35))
        if any(feature.has_money_amount for feature in features):
            breakdown.append(("ocr_has_money_amount", 25))
        if any(feature.has_bonus_or_promo for feature in features):
            breakdown.append(("ocr_has_bonus_or_promo", 25))
        if any(feature.has_payment_words for feature in features):
            breakdown.append(("ocr_has_withdraw_or_deposit", 20))
        if any(feature.has_crypto for feature in features):
            breakdown.append(("ocr_has_crypto_or_usdt", 20))
        if attachments and account_age_days is not None and account_age_days <= settings.new_account_days:
            breakdown.append(("new_account_with_image", 15))
        score = min(sum(points for _reason, points in breakdown), 100)
        risk = MediaRiskResult(
            score=score,
            breakdown=tuple(breakdown),
            requires_review=settings.medium_risk_threshold <= score < settings.high_risk_threshold,
            high_risk=score >= settings.high_risk_threshold,
        )
        logger.info("Media risk calculated score=%s high_risk=%s requires_review=%s breakdown=%s", risk.score, risk.high_risk, risk.requires_review, risk.breakdown)
        return risk

    def _is_short_or_only_mention(self, message_text: str, short_text_length: int) -> bool:
        visible_text = self.MENTION_RE.sub("", message_text or "").strip()
        return len(visible_text) <= short_text_length
