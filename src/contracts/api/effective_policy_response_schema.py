from src.contracts.api.api_model import ApiModel


class EffectivePolicyResponseSchema(ApiModel):
    correlation_id: str
    policies: tuple[dict[str, str | bool | int | float], ...]
