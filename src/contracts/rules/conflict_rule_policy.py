from pydantic import BaseModel, ConfigDict


class ConflictRulePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    description: str
    condition: str
    action: str
