# server/config/settings.py
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # App
    app_name: str = Field(default="AI Gmail Agent Backend")
    debug: bool = Field(default=False)

    # Groq API settings
    groq_api_key: str = Field(
        ...,
        description="Groq API key",
        env="GROQ_API_KEY",
    )
    # Recommended models: llama3-70b-8192, mixtral-8x7b-32768, gemma-7b-it
    groq_model: str = Field(
        default="llama3-70b-8192",
        env="GROQ_MODEL",
    )

    # Embeddings (Groq currently does not host embeddings, keeping Gemini or using another provider is recommended)
    # Using Gemini/OpenAI/HuggingFace for embeddings while using Groq for generation is a common pattern.
    # Leaving existing config for embeddings or requiring a separate provider.
    gemini_api_key: str = Field(
        default="",
        description="Google Gemini API key for embeddings (optional if using other)",
        env="GEMINI_API_KEY",
    )


    # Database / Memory storage
    pg_dsn: str = Field(..., env="PG_DSN")
    pg_pool_min_size: int = Field(default=1)
    pg_pool_max_size: int = Field(default=5)
    memory_table: str = Field(default="email_memory")

    # Active emails table name (short-term conversation memory)
    active_emails_table: str = Field(default="agent_active_emails")

    # v2-style config
    model_config = SettingsConfigDict(
        env_file="server/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()