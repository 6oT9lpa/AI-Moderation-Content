from src.contracts.api.api_model import ApiModel


class ApiAckSchema(ApiModel):
    correlation_id: str
    event_id: int
    status: str
