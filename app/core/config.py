"""Application configuration"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # OpenAI
    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    chat_model: str = "gpt-4o"
    chat_model_mini: str = "gpt-4o-mini"
    max_context_chunks: int = 10

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    # App
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    cors_origins: str = "*"  # Comma-separated list of allowed origins

    # Upload & Storage
    max_upload_size_mb: int = 50
    upload_dir: str = "./uploads"
    use_supabase_storage: bool = True
    storage_bucket_name: str = "pdf-uploads"

    # Database
    database_url: Optional[str] = None


# Global settings instance
settings = Settings()
