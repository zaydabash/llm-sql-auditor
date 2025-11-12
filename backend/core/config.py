"""Application configuration."""

import os
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    openai_api_key: str = ""
    log_level: str = "INFO"
    demo_db_path: str = "backend/db/demo.sqlite"
    default_dialect: Literal["postgres", "sqlite"] = "postgres"
    max_query_length: int = 100_000
    max_schema_length: int = 500_000
    llm_timeout: int = 30
    llm_max_retries: int = 3

    class Config:
        env_prefix = "SQLAUDITOR_"
        case_sensitive = False
        env_file = ".env"


settings = Settings()
