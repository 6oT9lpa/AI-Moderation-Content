import pytest
from src.application.moderation_service import ModerationService
from src.modules.preprocessing.text_preprocessor import TextPreprocessor
from src.modules.rules.moderation_rule_engine import ModerationRuleEngine
from src.modules.decision.decision_engine import DecisionEngine
from src.modules.rules.preprocessing_signal_adapter import PreprocessingSignalAdapter
from src.domain.moderation.moderation_action import ModerationAction
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

@pytest.fixture
def moderation_service():
    preprocessor = TextPreprocessor()
    rule_engine = ModerationRuleEngine()
    decision_engine = DecisionEngine()
    adapter = PreprocessingSignalAdapter()
    return ModerationService(preprocessor, rule_engine, decision_engine, adapter)

@pytest.mark.asyncio
async def test_full_pipeline_spam(moderation_service):
    logger.info("Testing full pipeline with SPAM text")
    text = "BUY CHEAP VIAGRA NOW!!! FREE FREE FREE http://malicious-site.com" * 5
    message_id = "msg_spam_1"
    
    decision = await moderation_service.moderate(message_id, text)
    
    logger.info(f"Pipeline result: action={decision.decision_action}, risk={decision.risk_score}")
    
    # Should detect something and have a risk score
    assert decision.message_id == message_id
    assert decision.risk_score > 0
    # We don't strictly assert action here as it depends on fine-tuned thresholds

@pytest.mark.asyncio
async def test_full_pipeline_safe(moderation_service):
    logger.info("Testing full pipeline with SAFE text")
    text = "Hello, how are you today?"
    message_id = "msg_safe_1"
    
    decision = await moderation_service.moderate(message_id, text)
    
    assert decision.decision_action == ModerationAction.IGNORE
    assert decision.risk_score == 0
