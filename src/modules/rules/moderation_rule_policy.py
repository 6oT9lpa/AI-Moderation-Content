from pydantic import BaseModel, ConfigDict, Field

from src.domain.moderation.moderation_label import ModerationLabel
from src.modules.rules.confidence_threshold_policy import ConfidenceThresholdPolicy
from src.modules.rules.conflict_rule_policy import ConflictRulePolicy
from src.modules.rules.label_risk_policy import LabelRiskPolicy
from src.modules.rules.model_agreement_policy import ModelAgreementPolicy
from src.modules.rules.risk_score_policy import RiskScorePolicy
from src.modules.rules.source_weight_policy import SourceWeightPolicy


class ModerationRulePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str
    version: str
    risk_score: RiskScorePolicy = Field(default_factory=RiskScorePolicy)
    source_weights: SourceWeightPolicy = Field(default_factory=SourceWeightPolicy)
    label_weights: LabelRiskPolicy = Field(default_factory=LabelRiskPolicy)
    confidence_thresholds: ConfidenceThresholdPolicy = Field(
        default_factory=ConfidenceThresholdPolicy
    )
    severity_multipliers: dict[int, float] = Field(default_factory=dict)
    primary_label_priority: list[ModerationLabel] = Field(default_factory=list)
    conflict_rules: list[ConflictRulePolicy] = Field(default_factory=list)
    model_agreement: ModelAgreementPolicy = Field(default_factory=ModelAgreementPolicy)
