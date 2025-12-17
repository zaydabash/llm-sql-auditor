"""Application configuration."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Core settings
    log_level: str = Field(default="INFO", alias="SQLAUDITOR_LOG_LEVEL")
    demo_db: str = Field(default="./demo.db", alias="SQLAUDITOR_DEMO_DB")
    default_dialect: str = Field(default="postgres", alias="DEFAULT_DIALECT")

    # LLM settings
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    llm_model: str = Field(default="gpt-4-turbo-preview", alias="SQLAUDITOR_LLM_MODEL")
    llm_temperature: float = Field(default=0.1, alias="SQLAUDITOR_LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2000, alias="SQLAUDITOR_LLM_MAX_TOKENS")
    llm_timeout: int = Field(default=30, alias="SQLAUDITOR_LLM_TIMEOUT")
    llm_budget_monthly: float = Field(default=100.0, alias="SQLAUDITOR_LLM_BUDGET_MONTHLY")
    llm_enable_cost_tracking: bool = Field(default=True, alias="SQLAUDITOR_LLM_ENABLE_COST_TRACKING")

    # Security settings
    require_auth: bool = Field(default=False, alias="SQLAUDITOR_REQUIRE_AUTH")
    api_key: Optional[str] = Field(default=None, alias="SQLAUDITOR_API_KEY")
    cors_origins: str = Field(default="http://localhost:5173", alias="SQLAUDITOR_CORS_ORIGINS")

    # Input validation
    max_schema_length: int = Field(default=50000, alias="SQLAUDITOR_MAX_SCHEMA_LENGTH")
    max_query_length: int = Field(default=10000, alias="SQLAUDITOR_MAX_QUERY_LENGTH")
    sqlite_connection_string: str = ""
    postgres_url: Optional[str] = Field(default=None, alias="SQLAUDITOR_POSTGRES_URL")
    enable_explain: bool = False



    class Config:
        env_prefix = "SQLAUDITOR_"
        case_sensitive = False
        env_file = ".env"


settings = Settings()
