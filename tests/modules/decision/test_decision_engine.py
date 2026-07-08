import pytest
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.rule_evaluation_result import RuleEvaluationResult
from src.domain.rules.model_agreement import ModelAgreement
from src.domain.rules.signal_source import SignalSource
from src.domain.decision.moderation_mode import ModerationMode
from src.modules.decision.decision_engine import DecisionEngine
from src.modules.decision.decision_policy import DecisionPolicy
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
    if decision.decision_action == ModerationAction.DELETE_WARN:
        assert decision.action_plan.actions == [ModerationAction.DELETE, ModerationAction.WARN]
    assert decision.action_required


def test_decision_engine_delete_warn_expands_to_executable_actions():
    policy = DecisionPolicy.model_validate(
        {
            "policy_id": "decision-test",
            "version": "1.0",
            "action_thresholds": {
                "IGNORE": 0,
                "LOG": 10,
                "REVIEW": 40,
                "WARN": 50,
                "DELETE": 70,
                "DELETE_WARN": 80,
                "TIMEOUT": 90,
                "BAN": 95,
            },
            "action_bundles": {
                "DELETE_WARN": ["DELETE", "WARN"],
            },
            "action_priority": ["BAN", "TIMEOUT", "DELETE_WARN", "DELETE", "WARN", "REVIEW", "LOG", "IGNORE"],
        },
    )
    decision_engine = DecisionEngine(policy=policy)
    rule_result = _make_rule_result(
        primary_label=ModerationLabel.ADVERTISEMENT,
        confidence=0.9,
        severity=3,
        risk_score=85.0,
    )

    decision = decision_engine.decide("msg_delete_warn_bundle", rule_result)

    assert decision.decision_action == ModerationAction.DELETE_WARN
    assert decision.action_plan.actions == [ModerationAction.DELETE, ModerationAction.WARN]
    assert decision.action_plan.required_actions == [ModerationAction.DELETE, ModerationAction.WARN]


def test_decision_engine_model_disagreement_forces_review_before_label_override(structured_test_logger):
    policy = DecisionPolicy.model_validate(
        {
            "policy_id": "decision-test",
            "version": "1.0",
            "label_overrides": {
                "THREAT": "DELETE",
            },
            "action_priority": ["DELETE", "REVIEW", "IGNORE"],
            "review_on_model_disagreement": True,
        },
    )
    decision_engine = DecisionEngine(policy=policy)
    rule_result = _make_rule_result(
        primary_label=ModerationLabel.THREAT,
        confidence=0.95,
        severity=5,
        risk_score=90.0,
        model_agreement=ModelAgreement(
            agreeing_sources=[],
            disagreeing_sources=[SignalSource.RUBERT, SignalSource.QWEN],
            agreement_score=0.7,
            high_confidence_disagreement=True,
            disagreement_reason="RuBERT and Qwen disagree",
        ),
    )

    decision = decision_engine.decide("msg_disagreement", rule_result)
    structured_test_logger(
        "detection",
        {
            "expected_action": "REVIEW",
            "actual_action": decision.decision_action,
            "reason": decision.reason,
        },
    )

    assert decision.decision_action == ModerationAction.REVIEW


def test_decision_engine_low_confidence_label_override_downgrades_to_review():
    policy = DecisionPolicy.model_validate(
        {
            "policy_id": "decision-test",
            "version": "1.0",
            "label_overrides": {
                "SCAM": "DELETE",
            },
            "min_confidence_for_action": 0.8,
            "review_on_low_confidence_high_risk": True,
            "action_priority": ["DELETE", "REVIEW", "IGNORE"],
        },
    )
    decision_engine = DecisionEngine(policy=policy)
    rule_result = _make_rule_result(
        primary_label=ModerationLabel.SCAM,
        confidence=0.55,
        severity=4,
        risk_score=85.0,
    )

    decision = decision_engine.decide("msg_low_conf_override", rule_result)

    assert decision.decision_action == ModerationAction.REVIEW


def test_decision_engine_passive_mode_caps_destructive_action():
    policy = DecisionPolicy.model_validate(
        {
            "policy_id": "decision-test",
            "version": "1.0",
            "mode": "PASSIVE",
            "label_overrides": {
                "THREAT": "DELETE",
            },
            "passive_mode_adjustments": {
                "max_action": "REVIEW",
            },
            "action_priority": ["DELETE", "REVIEW", "IGNORE"],
        },
    )
    decision_engine = DecisionEngine(policy=policy)
    rule_result = _make_rule_result(
        primary_label=ModerationLabel.THREAT,
        confidence=0.95,
        severity=5,
        risk_score=90.0,
    )

    decision = decision_engine.decide("msg_passive", rule_result)

    assert decision.decision_action == ModerationAction.REVIEW
    assert decision.action_plan.actions == [ModerationAction.REVIEW]
    assert decision.metadata["mode"] == ModerationMode.PASSIVE.value


def test_decision_engine_builds_required_action_bundle_for_ban(structured_test_logger):
    policy = DecisionPolicy.model_validate(
        {
            "policy_id": "decision-test",
            "version": "1.0",
            "label_overrides": {
                "THREAT": "BAN",
            },
            "action_bundles": {
                "BAN": ["DELETE", "BAN"],
            },
            "action_priority": ["BAN", "DELETE", "REVIEW", "IGNORE"],
        },
    )
    decision_engine = DecisionEngine(policy=policy)
    rule_result = _make_rule_result(
        primary_label=ModerationLabel.THREAT,
        confidence=0.95,
        severity=5,
        risk_score=96.0,
    )

    decision = decision_engine.decide("msg_ban_bundle", rule_result)
    structured_test_logger(
        "detection",
        {
            "expected_primary_action": "BAN",
            "expected_actions": ["DELETE", "BAN"],
            "actual_primary_action": decision.decision_action,
            "actual_actions": decision.action_plan.actions,
            "required_actions": decision.action_plan.required_actions,
        },
    )

    assert decision.decision_action == ModerationAction.BAN
    assert decision.action_plan.actions == [ModerationAction.DELETE, ModerationAction.BAN]
    assert decision.action_plan.required_actions == [ModerationAction.DELETE]
    assert decision.action_required


def test_decision_engine_low_confidence_bundle_is_downgraded_before_plan():
    policy = DecisionPolicy.model_validate(
        {
            "policy_id": "decision-test",
            "version": "1.0",
            "label_overrides": {
                "SCAM": "BAN",
            },
            "action_bundles": {
                "BAN": ["DELETE", "BAN"],
            },
            "min_confidence_for_action": 0.8,
            "review_on_low_confidence_high_risk": True,
            "action_priority": ["BAN", "DELETE", "REVIEW", "IGNORE"],
        },
    )
    decision_engine = DecisionEngine(policy=policy)
    rule_result = _make_rule_result(
        primary_label=ModerationLabel.SCAM,
        confidence=0.55,
        severity=4,
        risk_score=92.0,
    )

    decision = decision_engine.decide("msg_low_conf_bundle", rule_result)

    assert decision.decision_action == ModerationAction.REVIEW
    assert decision.action_plan.actions == [ModerationAction.REVIEW]


def _make_rule_result(
    *,
    primary_label: ModerationLabel,
    confidence: float,
    severity: int,
    risk_score: float,
    model_agreement: ModelAgreement | None = None,
) -> RuleEvaluationResult:
    return RuleEvaluationResult(
        signals=[],
        labels=[primary_label],
        primary_label=primary_label,
        confidence=confidence,
        severity=severity,
        risk_score=risk_score,
        risk_breakdown=[],
        matched_rules=[],
        conflicts=[],
        model_agreement=model_agreement
        or ModelAgreement(agreeing_sources=[], disagreeing_sources=[], agreement_score=1.0),
        policy_id="test",
        policy_version="1.0",
    )
