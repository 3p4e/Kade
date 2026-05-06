from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB
    database_url: str = Field(
        default="postgresql+asyncpg://coa:coa_secret@localhost:5432/coa_tracker",
        alias="DATABASE_URL",
    )

    # Auth
    jwt_secret: str = Field(default="dev-secret-change-me", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_ttl_min: int = Field(default=60, alias="ACCESS_TOKEN_TTL_MIN")

    # Storage
    data_dir: Path = Field(default=Path("/data/coa_pdfs"), alias="DATA_DIR")

    # OCR
    ocr_lang: str = Field(default="eng", alias="OCR_LANG")

    # Embeddings
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL",
    )
    embedding_dim: int = Field(default=384, alias="EMBEDDING_DIM")

    # LLM (RAG answer synthesis)
    llm_provider: str = Field(default="anthropic", alias="LLM_PROVIDER")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-6", alias="ANTHROPIC_MODEL")

    # IMAP
    imap_host: str = Field(default="", alias="IMAP_HOST")
    imap_port: int = Field(default=993, alias="IMAP_PORT")
    imap_user: str = Field(default="", alias="IMAP_USER")
    imap_password: str = Field(default="", alias="IMAP_PASSWORD")
    imap_folder: str = Field(default="INBOX", alias="IMAP_FOLDER")
    imap_poll_seconds: int = Field(default=300, alias="IMAP_POLL_SECONDS")

    # Bootstrap admin
    bootstrap_admin_email: str = Field(
        default="admin@example.com", alias="BOOTSTRAP_ADMIN_EMAIL"
    )
    bootstrap_admin_password: str = Field(
        default="admin", alias="BOOTSTRAP_ADMIN_PASSWORD"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
