from src.contracts.api.api_model import ApiModel


class ApiErrorSchema(ApiModel):
    code: str
    message: str
    correlation_id: str
