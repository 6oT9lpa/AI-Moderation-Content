from __future__ import annotations

from pydantic import ConfigDict, Field

from src.modules.preprocessing.rules.preprocessing_rule_policy import PreprocessingRulePolicy


class PreprocessingRepeatedWordsPolicy(PreprocessingRulePolicy):
    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum_token_count: int = Field(default=5, ge=1)
    minimum_repetition_ratio: float = Field(default=0.5, ge=0.0, le=1.0)
