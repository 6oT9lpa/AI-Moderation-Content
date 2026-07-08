from __future__ import annotations

from typing import Any

from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.domain.decision.moderation_decision import ModerationDecision
from src.domain.rules.moderation_signal import ModerationSignal
from src.infrastructure.logging.logger import get_logger
from src.modules.decision.decision_engine import DecisionEngine
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
    ):
        self._preprocessor = preprocessor
        self._rule_engine = rule_engine
        self._decision_engine = decision_engine
        self._signal_adapter = signal_adapter

    async def moderate(
        self,
        message_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> ModerationDecision:
        logger.info("Moderation pipeline started message_id=%s text_length=%s", message_id, len(text))

        payload = MessagePreprocessInputSchema(
            message_id=message_id,
            raw_text=text,
            platform="unknown",
            guild_id="unknown",
            channel_id="unknown",
            user_id="unknown",
            metadata=metadata or {},
        )
        processed_context = await self._preprocessor.process(payload)

        preprocessing_matches = processed_context.metadata.get("preprocessing_rule_matches", [])
        signals: list[ModerationSignal] = []

        for match_data in preprocessing_matches:
            signals.extend(self._signal_adapter.adapt(match_data))

        logger.info(
            "Moderation preprocessing adapted message_id=%s preprocessing_matches=%s signal_count=%s",
            message_id,
            len(preprocessing_matches),
            len(signals),
        )

        rule_result = self._rule_engine.evaluate(message_id, signals)
        decision = self._decision_engine.decide(message_id, rule_result)

        logger.info(
            "Moderation pipeline finished message_id=%s action=%s risk_score=%s primary_label=%s",
            message_id,
            decision.decision_action,
            decision.risk_score,
            decision.primary_label,
        )
        return decision
