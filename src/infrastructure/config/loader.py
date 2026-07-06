from functools import lru_cache
from src.infrastructure.config.settings import Config


@lru_cache(maxsize=1)
def get_config() -> Config:
    # Singleton instance of Config, cached for performance
    return Config()


def reload_config() -> Config:
    # Clear the cache to force reloading the configuration
    get_config.cache_clear()
    return get_config()