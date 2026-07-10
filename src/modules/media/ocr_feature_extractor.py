from __future__ import annotations

import re

from src.domain.media.ocr_features import OcrFeatures
from src.domain.media.ocr_result import OcrResult
from src.infrastructure.logging import get_logger
from src.modules.media.media_rule_settings import MediaRuleSettings

logger = get_logger(__name__)


class OcrFeatureExtractor:
    DOMAIN_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,63}\b", re.IGNORECASE)
    MONEY_RE = re.compile(r"(?<!\d)(?:\d{1,3}(?:[ ,]\d{3})+|\d{4,})(?!\d)")

    def extract(
        self,
        result: OcrResult,
        settings: MediaRuleSettings,
        *,
        image_area: int | None = None,
    ) -> OcrFeatures:
        normalized_text = result.text.casefold().strip()
        density_denominator = image_area if image_area and image_area > 0 else 1_000
        features = OcrFeatures(
            text_density=round(min(len(normalized_text) * 10_000 / density_denominator, 1.0), 4),
            money_amounts=tuple(dict.fromkeys(self.MONEY_RE.findall(normalized_text))),
            domains=tuple(dict.fromkeys(match.lower() for match in self.DOMAIN_RE.findall(normalized_text))),
            casino_keywords=self._matched_keywords(normalized_text, settings.casino_keywords),
            money_keywords=self._matched_keywords(normalized_text, settings.money_keywords),
            bonus_keywords=self._matched_keywords(normalized_text, settings.bonus_keywords),
            payment_keywords=self._matched_keywords(normalized_text, settings.payment_keywords),
            fake_news_keywords=self._matched_keywords(normalized_text, settings.fake_news_keywords),
            crypto_keywords=self._matched_keywords(normalized_text, settings.crypto_keywords),
        )
        logger.info("OCR features extracted text_length=%s casino=%s money=%s payment=%s", len(normalized_text), features.has_casino, features.has_money_amount, features.has_payment_words)
        return features

    def _matched_keywords(self, text: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(keyword for keyword in keywords if keyword.casefold() in text)
