"""Application configuration via Pydantic settings."""

from functools import lru_cache

from pydantic import Field
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
