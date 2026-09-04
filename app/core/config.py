"""Application configuration via Pydantic settings."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for Tradux."""

    app_name: str = Field(default="Tradux", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    environment: str = Field(default="development", description="Runtime environment")
    debug: bool = Field(default=False, description="Debug mode")
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    api_v1_prefix: str = Field(default="/api/v1", description="API v1 route prefix")
    temp_dir: str = Field(default="temp", description="Temporary files directory")
    output_dir: str = Field(default="output", description="Output files directory")
    max_upload_size_mb: int = Field(
        default=50, description="Maximum upload file size in megabytes"
    )

    # Translation engine configuration
    translation_provider: str = Field(
        default="mock",
        description="Active translation provider: 'mock' or 'openai'",
    )
    translation_api_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="API base URL for OpenAI-compatible translation provider",
    )
    translation_api_key: SecretStr | None = Field(
        default=None,
        description="API secret key for translation provider",
    )
    translation_model: str = Field(
        default="gpt-4o-mini",
        description="Model name for translation provider",
    )
    translation_timeout_seconds: float = Field(
        default=30.0,
        description="HTTP timeout in seconds for translation provider",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
