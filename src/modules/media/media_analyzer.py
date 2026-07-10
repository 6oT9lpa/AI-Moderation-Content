from __future__ import annotations

from dataclasses import replace
from time import perf_counter

from src.application.ports.services.ocr_service import OcrService
from src.contracts.image_attachment_input_schema import ImageAttachmentInputSchema
from src.domain.media.ocr_result import OcrResult
from src.domain.media.ocr_status import OcrStatus
from src.domain.media.media_analysis_result import MediaAnalysisResult
from src.domain.media.media_attachment_analysis import MediaAttachmentAnalysis
from src.domain.moderation.scam_subtype import ScamSubtype
from src.infrastructure.logging import get_logger
from src.infrastructure.media.image_hash_calculator import ImageHashCalculator
from src.infrastructure.media.pillow_image_rasterizer import PillowImageRasterizer
from src.infrastructure.media.tesseract_ocr_service import TesseractOcrService
from src.modules.media.image_metadata_extractor import ImageMetadataExtractor
from src.modules.media.known_scam_image_hash_registry import KnownScamImageHashRegistry
from src.modules.media.known_scam_image_hash_config_loader import KnownScamImageHashConfigLoader
from src.modules.media.media_risk_scorer import MediaRiskScorer
from src.modules.media.media_rule_config_loader import MediaRuleConfigLoader
from src.modules.media.media_rule_engine import MediaRuleEngine
from src.modules.media.media_rule_settings import MediaRuleSettings
from src.modules.media.ocr_feature_extractor import OcrFeatureExtractor

logger = get_logger(__name__)


class MediaAnalyzer:
    def __init__(
        self,
        *,
        settings: MediaRuleSettings | None = None,
        metadata_extractor: ImageMetadataExtractor | None = None,
        hash_calculator: ImageHashCalculator | None = None,
        known_hash_registry: KnownScamImageHashRegistry | None = None,
        known_hash_config_path: str | None = None,
        ocr_service: OcrService | None = None,
        ocr_feature_extractor: OcrFeatureExtractor | None = None,
        risk_scorer: MediaRiskScorer | None = None,
        rule_engine: MediaRuleEngine | None = None,
    ) -> None:
        self._settings = settings or MediaRuleConfigLoader.load()
        rasterizer = PillowImageRasterizer(max_image_pixels=self._settings.max_image_pixels)
        self._metadata_extractor = metadata_extractor or ImageMetadataExtractor(rasterizer)
        self._hash_calculator = hash_calculator or ImageHashCalculator(rasterizer)
        self._known_hash_registry = known_hash_registry or KnownScamImageHashRegistry(
            KnownScamImageHashConfigLoader.load(known_hash_config_path),
            max_distance=self._settings.max_phash_distance,
        )
        self._ocr_service = ocr_service or TesseractOcrService(
            max_image_pixels=self._settings.max_image_pixels,
            max_text_length=self._settings.max_ocr_text_length,
        )
        self._ocr_feature_extractor = ocr_feature_extractor or OcrFeatureExtractor()
        self._risk_scorer = risk_scorer or MediaRiskScorer()
        self._rule_engine = rule_engine or MediaRuleEngine()
        logger.info("Media analyzer initialized settings_version=%s", self._settings.version)

    async def analyze(
        self,
        attachments: tuple[ImageAttachmentInputSchema, ...] | list[ImageAttachmentInputSchema],
        *,
        message_text: str,
        account_age_days: int | None = None,
        correlation_id: str | None = None,
    ) -> MediaAnalysisResult:
        started_at = perf_counter()
        image_attachments = self._select_attachments(tuple(attachments), correlation_id)
        logger.info(
            "Media stage=analysis status=started correlation_id=%s attachment_count=%s text_length=%s",
            correlation_id,
            len(image_attachments),
            len(message_text),
        )
        analyses: list[MediaAttachmentAnalysis] = []
        for attachment in image_attachments:
            analyses.append(await self._analyze_attachment(attachment, correlation_id))
        immutable_analyses = tuple(analyses)
        risk = self._risk_scorer.calculate(immutable_analyses, message_text, account_age_days, self._settings)
        rule_matches = self._rule_engine.evaluate(immutable_analyses, risk)
        labels = tuple(sorted({label for match in rule_matches for label in match.labels}, key=lambda label: label.value))
        result = MediaAnalysisResult(
            attachments=immutable_analyses,
            rule_matches=rule_matches,
            risk=risk,
            labels=labels,
            scam_subtype=self._resolve_scam_subtype(immutable_analyses),
        )
        logger.info(
            "Media stage=analysis status=completed correlation_id=%s image_count=%s risk_score=%s labels=%s subtype=%s latency_ms=%s",
            correlation_id,
            result.image_count,
            result.risk.score,
            [label.value for label in result.labels],
            result.scam_subtype,
            round((perf_counter() - started_at) * 1000),
        )
        return result

    async def _analyze_attachment(
        self,
        attachment: ImageAttachmentInputSchema,
        correlation_id: str | None,
    ) -> MediaAttachmentAnalysis:
        metadata = self._metadata_extractor.extract(attachment)
        hashes = self._hash_calculator.calculate(attachment.image_bytes)
        known_scam_match = self._known_hash_registry.find_match(hashes)
        try:
            ocr_result = await self._ocr_service.extract(attachment)
        except Exception as exc:
            logger.warning(
                "Media stage=ocr status=failed correlation_id=%s attachment_id=%s error_type=%s",
                correlation_id,
                attachment.attachment_id,
                type(exc).__name__,
            )
            ocr_result = OcrResult(status=OcrStatus.FAILED, error="ocr_service_failed")
        bounded_ocr_result = self._bound_ocr_text(ocr_result, attachment.attachment_id, correlation_id)
        image_area = metadata.width * metadata.height if metadata.width and metadata.height else None
        ocr_features = self._ocr_feature_extractor.extract(
            bounded_ocr_result,
            self._settings,
            image_area=image_area,
        )
        return MediaAttachmentAnalysis(
            attachment_id=attachment.attachment_id,
            metadata=metadata,
            hashes=hashes,
            ocr_result=bounded_ocr_result,
            ocr_features=ocr_features,
            known_scam_match=known_scam_match,
        )

    def _select_attachments(
        self,
        attachments: tuple[ImageAttachmentInputSchema, ...],
        correlation_id: str | None,
    ) -> tuple[ImageAttachmentInputSchema, ...]:
        accepted: list[ImageAttachmentInputSchema] = []
        for attachment in attachments:
            actual_size = len(attachment.image_bytes) if attachment.image_bytes else attachment.file_size or 0
            if actual_size > self._settings.max_image_bytes:
                logger.warning(
                    "Media stage=input status=rejected correlation_id=%s attachment_id=%s reason=byte_limit actual_bytes=%s max_bytes=%s",
                    correlation_id,
                    attachment.attachment_id,
                    actual_size,
                    self._settings.max_image_bytes,
                )
                continue
            accepted.append(attachment)

        if len(accepted) <= self._settings.max_image_attachments:
            return tuple(accepted)

        logger.warning(
            "Media stage=input status=truncated correlation_id=%s accepted_count=%s max_attachments=%s",
            correlation_id,
            len(accepted),
            self._settings.max_image_attachments,
        )
        return tuple(accepted[: self._settings.max_image_attachments])

    def _bound_ocr_text(
        self,
        result: OcrResult,
        attachment_id: str,
        correlation_id: str | None,
    ) -> OcrResult:
        if len(result.text) <= self._settings.max_ocr_text_length:
            return result
        logger.warning(
            "Media stage=ocr status=truncated correlation_id=%s attachment_id=%s original_length=%s max_length=%s",
            correlation_id,
            attachment_id,
            len(result.text),
            self._settings.max_ocr_text_length,
        )
        return replace(result, text=result.text[: self._settings.max_ocr_text_length])

    def _resolve_scam_subtype(
        self,
        attachments: tuple[MediaAttachmentAnalysis, ...],
    ) -> ScamSubtype | None:
        for attachment in attachments:
            if attachment.known_scam_match and attachment.known_scam_match.scam_subtype:
                return attachment.known_scam_match.scam_subtype
        features = [attachment.ocr_features for attachment in attachments]
        if any(feature.has_casino for feature in features):
            return ScamSubtype.CASINO_BONUS
        if any(feature.has_crypto for feature in features):
            return ScamSubtype.CRYPTO_SCAM
        if any(feature.has_fake_news for feature in features):
            return ScamSubtype.FAKE_NEWS_AD
        if any(feature.has_bonus_or_promo for feature in features):
            return ScamSubtype.FAKE_GIVEAWAY
        if any(feature.has_payment_words for feature in features):
            return ScamSubtype.FAKE_PAYMENT_PROOF
        return None
