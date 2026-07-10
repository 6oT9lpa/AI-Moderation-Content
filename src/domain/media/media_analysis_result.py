from __future__ import annotations

from dataclasses import dataclass

from src.domain.media.media_attachment_analysis import MediaAttachmentAnalysis
from src.domain.media.media_risk_result import MediaRiskResult
from src.domain.media.media_rule_match import MediaRuleMatch
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.moderation.scam_subtype import ScamSubtype


@dataclass(slots=True, frozen=True)
class MediaAnalysisResult:
    attachments: tuple[MediaAttachmentAnalysis, ...]
    rule_matches: tuple[MediaRuleMatch, ...]
    risk: MediaRiskResult
    labels: tuple[ModerationLabel, ...]
    scam_subtype: ScamSubtype | None

    @property
    def image_count(self) -> int:
        return len(self.attachments)

    @property
    def known_scam_hash_match(self) -> bool:
        return any(attachment.known_scam_hash_match for attachment in self.attachments)

    def to_dict(self, *, include_ocr_text: bool = True) -> dict[str, object]:
        return {
            "image_count": self.image_count,
            "attachments": [
                attachment.to_dict(include_ocr_text=include_ocr_text)
                for attachment in self.attachments
            ],
            "media_rule_matches": [match.to_dict() for match in self.rule_matches],
            "media_risk_score": self.risk.score,
            "media_risk": self.risk.to_dict(),
            "media_labels": [label.value for label in self.labels],
            "scam_subtype": self.scam_subtype.value if self.scam_subtype else None,
            "known_scam_hash_match": self.known_scam_hash_match,
        }
