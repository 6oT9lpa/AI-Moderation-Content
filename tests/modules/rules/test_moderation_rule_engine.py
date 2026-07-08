import pytest
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.moderation_signal import ModerationSignal
from src.domain.rules.signal_source import SignalSource
from src.modules.rules.moderation_rule_engine import ModerationRuleEngine
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
