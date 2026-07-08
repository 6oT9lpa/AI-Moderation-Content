import pytest
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.rule_evaluation_result import RuleEvaluationResult
from src.domain.rules.model_agreement import ModelAgreement
from src.modules.decision.decision_engine import DecisionEngine
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

@pytest.fixture
def decision_engine():
    return DecisionEngine()

def test_decision_engine_safe(decision_engine):
    logger.info("Testing Decision Engine with SAFE result")
    rule_result = RuleEvaluationResult(
        signals=[],
        labels=[ModerationLabel.SAFE],
        primary_label=ModerationLabel.SAFE,
        confidence=1.0,
        severity=0,
        risk_score=0.0,
        risk_breakdown=[],
        matched_rules=[],
        conflicts=[],
        model_agreement=ModelAgreement(agreeing_sources=[], disagreeing_sources=[], agreement_score=1.0),
        policy_id="test",
        policy_version="1.0"
    )
    
    decision = decision_engine.decide("msg_1", rule_result)
    
    assert decision.decision_action == ModerationAction.IGNORE
    assert not decision.action_required

def test_decision_engine_high_risk(decision_engine):
    logger.info("Testing Decision Engine with high risk result")
    rule_result = RuleEvaluationResult(
        signals=[],
        labels=[ModerationLabel.THREAT],
        primary_label=ModerationLabel.THREAT,
        confidence=0.9,
        severity=5,
        risk_score=85.0,
        risk_breakdown=[],
        matched_rules=[],
        conflicts=[],
        model_agreement=ModelAgreement(agreeing_sources=[], disagreeing_sources=[], agreement_score=1.0),
        policy_id="test",
        policy_version="1.0"
    )
    
    decision = decision_engine.decide("msg_2", rule_result)
    
    # Based on default policy, 85 risk should be DELETE_WARN or similar
    assert decision.decision_action in {ModerationAction.DELETE, ModerationAction.DELETE_WARN}
    assert decision.action_required
