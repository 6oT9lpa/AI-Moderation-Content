import uvicorn

from src.infrastructure.api.api_settings import ApiSettings
from src.infrastructure.config.loader import get_config
from src.infrastructure.logging import get_logger
from src.presentation.api.api_application_factory import create_api_application

logger = get_logger(__name__)
settings = ApiSettings()

if settings.api_host not in {"127.0.0.1", "::1", "localhost"}:
    logger.warning("API is configured for a non-loopback host")

app = create_api_application(get_config().database_url, settings)


if __name__ == "__main__":
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
