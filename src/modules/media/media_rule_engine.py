from __future__ import annotations

from src.domain.media.media_attachment_analysis import MediaAttachmentAnalysis
from src.domain.media.media_risk_result import MediaRiskResult
from src.domain.media.media_rule_match import MediaRuleMatch
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.signal_source import SignalSource
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class MediaRuleEngine:
    def evaluate(
        self,
        attachments: tuple[MediaAttachmentAnalysis, ...],
        risk: MediaRiskResult,
    ) -> tuple[MediaRuleMatch, ...]:
        matches: list[MediaRuleMatch] = []
        if any(attachment.known_scam_hash_match for attachment in attachments):
            matches.append(
                MediaRuleMatch(
                    rule_id="media.image.known_scam_hash",
                    source=SignalSource.IMAGE,
                    labels=(ModerationLabel.SCAM, ModerationLabel.IMAGE_SCAM),
                    severity=5,
                    confidence=0.99,
                    risk_weight=70,
                    reason="known_scam_image_hash",
                    evidence={
                        "matched_hashes": [
                            attachment.known_scam_match.to_dict()
                            for attachment in attachments
                            if attachment.known_scam_match is not None
                        ],
                    },
                )
            )
        elif risk.high_risk and self._has_ocr_scam_evidence(attachments):
            matches.append(
                MediaRuleMatch(
                    rule_id="media.ocr.high_risk_scam",
                    source=SignalSource.OCR,
                    labels=(
                        ModerationLabel.SCAM,
                        ModerationLabel.ADVERTISEMENT,
                        ModerationLabel.IMAGE_SCAM,
                    ),
                    severity=4,
                    confidence=0.9,
                    risk_weight=70,
                    reason="high_media_risk_from_ocr",
                    evidence={"media_risk": risk.to_dict()},
                )
            )
        elif risk.requires_review and self._has_ocr_scam_evidence(attachments):
            matches.append(
                MediaRuleMatch(
                    rule_id="media.ocr.review_required",
                    source=SignalSource.OCR,
                    labels=(ModerationLabel.IMAGE_SCAM,),
                    severity=3,
                    confidence=0.8,
                    risk_weight=40,
                    reason="medium_media_risk_requires_review",
                    evidence={"media_risk": risk.to_dict()},
                )
            )
        logger.info("Media rules evaluated attachment_count=%s rule_matches=%s", len(attachments), len(matches))
        return tuple(matches)

    def _has_ocr_scam_evidence(self, attachments: tuple[MediaAttachmentAnalysis, ...]) -> bool:
        return any(
            feature.has_casino
            or feature.has_money_amount
            or feature.has_bonus_or_promo
            or feature.has_payment_words
            or feature.has_fake_news
            or feature.has_crypto
            for feature in (attachment.ocr_features for attachment in attachments)
        )
