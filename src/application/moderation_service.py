from __future__ import annotations

from typing import Any

from src.contracts.image_attachment_input_schema import ImageAttachmentInputSchema
from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.domain.decision.moderation_decision import ModerationDecision
from src.domain.rules.moderation_signal import ModerationSignal
from src.infrastructure.logging.logger import get_logger
from src.modules.decision.decision_engine import DecisionEngine
from src.modules.media.media_analyzer import MediaAnalyzer
from src.modules.media.media_signal_adapter import MediaSignalAdapter
from src.modules.preprocessing.text_preprocessor import TextPreprocessor
from src.modules.rules.moderation_rule_engine import ModerationRuleEngine
from src.modules.rules.preprocessing_signal_adapter import PreprocessingSignalAdapter

logger = get_logger(__name__)


class ModerationService:
    def __init__(
        self,
        preprocessor: TextPreprocessor,
        rule_engine: ModerationRuleEngine,
        decision_engine: DecisionEngine,
        signal_adapter: PreprocessingSignalAdapter,
        media_analyzer: MediaAnalyzer | None = None,
        media_signal_adapter: MediaSignalAdapter | None = None,
    ):
        self._preprocessor = preprocessor
        self._rule_engine = rule_engine
        self._decision_engine = decision_engine
        self._signal_adapter = signal_adapter
        self._media_analyzer = media_analyzer or MediaAnalyzer()
        self._media_signal_adapter = media_signal_adapter or MediaSignalAdapter()

    async def moderate(
        self,
        message_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        attachments: tuple[ImageAttachmentInputSchema, ...] = (),
    ) -> ModerationDecision:
        logger.info("Moderation pipeline started message_id=%s text_length=%s", message_id, len(text))

        payload = MessagePreprocessInputSchema(
            message_id=message_id,
            raw_text=text,
            platform="unknown",
            guild_id="unknown",
            channel_id="unknown",
            user_id="unknown",
            has_attachments=bool(attachments),
            attachment_count=len(attachments),
            metadata=metadata or {},
        )
        processed_context = await self._preprocessor.process(payload)

        preprocessing_matches = processed_context.metadata.get("preprocessing_rule_matches", [])
        signals: list[ModerationSignal] = []

        for match_data in preprocessing_matches:
            signals.extend(self._signal_adapter.adapt(match_data))

        media_result = None
        if attachments:
            media_result = await self._media_analyzer.analyze(
                attachments,
                message_text=text,
                account_age_days=processed_context.account_age_days,
                correlation_id=message_id,
            )
            for match in media_result.rule_matches:
                signals.extend(self._media_signal_adapter.adapt(match))

        logger.info(
            "Moderation signals adapted message_id=%s preprocessing_matches=%s media_matches=%s signal_count=%s",
            message_id,
            len(preprocessing_matches),
            len(media_result.rule_matches) if media_result else 0,
            len(signals),
        )

        rule_result = self._rule_engine.evaluate(message_id, signals)
        decision = self._decision_engine.decide(message_id, rule_result)
        if media_result is not None:
            decision = decision.model_copy(
                update={
                    "metadata": {
                        **decision.metadata,
                        "media_analysis": media_result.to_dict(include_ocr_text=False),
                    },
                    "media_analysis": media_result,
                },
            )

        logger.info(
            "Moderation pipeline finished message_id=%s action=%s risk_score=%s primary_label=%s",
            message_id,
            decision.decision_action,
            decision.risk_score,
            decision.primary_label,
        )
        return decision
