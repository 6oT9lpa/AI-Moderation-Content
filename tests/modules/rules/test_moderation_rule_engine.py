import pytest
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.moderation_signal import ModerationSignal
from src.domain.rules.signal_source import SignalSource
from src.modules.rules.moderation_rule_engine import ModerationRuleEngine
from src.contracts.rules.moderation_rule_policy import ModerationRulePolicy
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

@pytest.fixture
def rule_engine():
    return ModerationRuleEngine()

def test_rule_engine_empty_signals(rule_engine):
    logger.info("Testing Rule Engine with empty signals")
    result = rule_engine.evaluate("msg_1", [])
    
    assert result.primary_label == ModerationLabel.SAFE
    assert result.risk_score == 0.0
    assert len(result.signals) == 0

def test_rule_engine_single_signal(rule_engine):
    logger.info("Testing Rule Engine with single SPAM signal")
    signal = ModerationSignal(
        source=SignalSource.PREPROCESSING,
        label=ModerationLabel.SPAM,
        confidence=0.8,
        severity=3,
        risk_weight=10,
        reason="Spam detected"
    )
    
    result = rule_engine.evaluate("msg_2", [signal])
    
    assert result.primary_label == ModerationLabel.SPAM
    assert result.risk_score > 0
    assert result.confidence == 0.8

def test_rule_engine_conflict_resolution(rule_engine):
    logger.info("Testing Rule Engine conflict resolution: SAFE vs SCAM")
    signals = [
        ModerationSignal(
            source=SignalSource.PREPROCESSING,
            label=ModerationLabel.SAFE,
            confidence=0.9,
            severity=0,
            risk_weight=0,
            reason="Looks safe"
        ),
        ModerationSignal(
            source=SignalSource.RUBERT,
            label=ModerationLabel.SCAM,
            confidence=0.7,
            severity=4,
            risk_weight=50,
            reason="Scam detected by model"
        )
    ]
    
    result = rule_engine.evaluate("msg_3", signals)
    
    # SAFE should be excluded from primary if harmful signals exist
    assert result.primary_label == ModerationLabel.SCAM
    assert any("safe" in c for c in result.conflicts)


def test_rule_engine_model_agreement_bonus_does_not_break_validation(rule_engine, structured_test_logger):
    signals = [
        ModerationSignal(
            source=SignalSource.RUBERT,
            label=ModerationLabel.SCAM,
            confidence=0.9,
            severity=4,
            risk_weight=40,
            reason="RuBERT scam signal",
            model_name="rubert",
            model_version="test",
        ),
        ModerationSignal(
            source=SignalSource.QWEN,
            label=ModerationLabel.SCAM,
            confidence=0.92,
            severity=4,
            risk_weight=45,
            reason="Qwen scam signal",
            model_name="qwen",
            model_version="test",
        ),
    ]

    result = rule_engine.evaluate("msg_model_agreement", signals)
    structured_test_logger(
        "detection",
        {
            "risk_score": result.risk_score,
            "agreement_score": result.model_agreement.agreement_score,
            "agreeing_sources": result.model_agreement.agreeing_sources,
        },
    )

    assert result.model_agreement.agreement_score > 1.0
    assert result.primary_label == ModerationLabel.SCAM


def test_rule_engine_clamps_total_risk_when_single_contribution_exceeds_100(rule_engine, structured_test_logger):
    signal = ModerationSignal(
        source=SignalSource.QWEN,
        label=ModerationLabel.THREAT,
        confidence=1.0,
        severity=5,
        risk_weight=120,
        reason="High confidence threat",
        model_name="qwen",
        model_version="test",
    )

    result = rule_engine.evaluate("msg_high_threat", [signal])
    structured_test_logger(
        "detection",
        {
            "risk_score": result.risk_score,
            "risk_breakdown": [item.model_dump(mode="json") for item in result.risk_breakdown],
        },
    )

    assert result.risk_score == 100.0
    assert result.risk_breakdown[0].contribution > 100.0


def test_rule_engine_uses_signal_risk_weight(rule_engine):
    low_signal = ModerationSignal(
        source=SignalSource.PREPROCESSING,
        label=ModerationLabel.URL,
        confidence=0.9,
        severity=3,
        risk_weight=5,
        reason="Low risk URL",
    )
    high_signal = ModerationSignal(
        source=SignalSource.PREPROCESSING,
        label=ModerationLabel.URL,
        confidence=0.9,
        severity=3,
        risk_weight=40,
        reason="High risk URL",
    )

    low_result = rule_engine.evaluate("msg_low_url", [low_signal])
    high_result = rule_engine.evaluate("msg_high_url", [high_signal])

    assert high_result.risk_score > low_result.risk_score


def test_rule_engine_specific_confidence_threshold_overrides_default():
    policy = ModerationRulePolicy.model_validate(
        {
            "policy_id": "threshold-test",
            "version": "1.0",
            "confidence_thresholds": {
                "default_min_confidence": 0.9,
                "per_source_min_confidence": {
                    "PREPROCESSING": 0.3,
                },
            },
            "primary_label_priority": ["SPAM", "SAFE"],
        },
    )
    engine = ModerationRuleEngine(policy=policy)
    signal = ModerationSignal(
        source=SignalSource.PREPROCESSING,
        label=ModerationLabel.SPAM,
        confidence=0.4,
        severity=3,
        risk_weight=20,
        reason="Preprocessing spam signal",
    )

    result = engine.evaluate("msg_threshold_override", [signal])

    assert result.signals == [signal]
    assert result.primary_label == ModerationLabel.SPAM
