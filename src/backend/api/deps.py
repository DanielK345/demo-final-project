from functools import lru_cache

from src.backend.config import Settings, get_settings


@lru_cache
def get_app_settings() -> Settings:
    return get_settings()
