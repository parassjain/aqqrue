import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class Settings:
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o")
    API_KEY: str = os.getenv("API_KEY", "")
    API_BASE: Optional[str] = os.getenv("API_BASE")
    SESSION_DATA_DIR: str = os.getenv("SESSION_DATA_DIR", "data/sessions")
    SANDBOX_TIMEOUT: int = int(os.getenv("SANDBOX_TIMEOUT", "30"))
    SANDBOX_MEMORY_LIMIT: str = os.getenv("SANDBOX_MEMORY_LIMIT", "512m")
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))


settings = Settings()


def get_litellm_kwargs() -> dict:
    """Return kwargs dict for litellm.completion() calls."""
    kwargs: dict = {
        "model": settings.MODEL_NAME,
        "api_key": settings.API_KEY,
    }
    if settings.API_BASE:
        kwargs["api_base"] = settings.API_BASE
    return kwargs
