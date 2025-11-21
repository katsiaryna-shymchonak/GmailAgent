"""Application settings and configuration"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    app_name: str = Field(default="AI Gmail Agent Backend")
    debug: bool = Field(default=False)

    # Gemini / Google Generative AI configuration
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash")
    embedding_model: str = Field(default="text-embedding-004")

    # Database / Memory storage configuration
    pg_dsn: str = Field(..., env="PG_DSN")
    pg_pool_min_size: int = Field(default=1)
    pg_pool_max_size: int = Field(default=5)
    memory_table: str = Field(default="email_memory")

    class Config:
        env_file = "server/.env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()  # type: ignore[arg-type]

