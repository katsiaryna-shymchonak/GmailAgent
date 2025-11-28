"""Application settings and configuration"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # App
    app_name: str = Field(default="AI Gmail Agent Backend")
    debug: bool = Field(default=False)

    # Gemini / Google Generative AI
    gemini_api_key: str = Field(
        ...,
        description="Google Gemini API key",
        env="GEMINI_API_KEY",  # accept either name
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        env="GEMINI_MODEL",
    )
    embedding_model: str = Field(
        default="text-embedding-004",
        env="EMBEDDING_MODEL",
    )

    # Database / Memory storage
    pg_dsn: str = Field(..., env="PG_DSN")
    pg_pool_min_size: int = Field(default=1)
    pg_pool_max_size: int = Field(default=5)
    memory_table: str = Field(default="email_memory")

    # v2-style config
    model_config = SettingsConfigDict(
        env_file="server/.env",      # change to ".env" if your file is in the project root
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
