"""Application configuration."""

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
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    rate_limit_per_minute: int = 10

    # Database connection strings for EXPLAIN
    postgres_connection_string: str = ""
    sqlite_connection_string: str = ""
    enable_explain: bool = False

    # Authentication
    api_key: str = ""
    require_auth: bool = False

    class Config:
        env_prefix = "SQLAUDITOR_"
        case_sensitive = False
        env_file = ".env"


settings = Settings()
