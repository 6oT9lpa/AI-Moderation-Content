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

    async def moderate(self, message_id: str, text: str, metadata: dict[str, Any] = None) -> ModerationDecision:
        logger.info(f"Starting moderation for message {message_id}")
        
        # 1. Preprocessing
        payload = MessagePreprocessInputSchema(
            message_id=message_id,
            raw_text=text,
            platform="unknown",
            guild_id="unknown",
            channel_id="unknown",
            user_id="unknown",
            metadata=metadata or {}
        )
        processed_context = await self._preprocessor.process(payload)
        
        # 2. Extract signals from preprocessing
        preprocessing_matches = processed_context.metadata.get("preprocessing_rule_matches", [])
        signals: list[ModerationSignal] = []
        for match_data in preprocessing_matches:
            signals.extend(self._signal_adapter.adapt(match_data))
            
        # 3. Rule Evaluation
        rule_result = self._rule_engine.evaluate(message_id, signals)
        
        # 4. Decision
        decision = self._decision_engine.decide(message_id, rule_result)
        
        logger.info(f"Moderation completed for {message_id}. Result: {decision.decision_action}")
        return decision
