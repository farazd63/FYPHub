"""Configuration for the FYPHub backend."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL

ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ROOT_ENV_PATH, override=False)


@dataclass(frozen=True)
class Settings:
    postgres_host: str
    postgres_port: int
    postgres_database: str
    postgres_user: str
    postgres_password: str
    session_lifetime_hours: int = 8
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_proposal_model: str = "llama3.1:8b"
    ollama_agent_model: str = "llama3.1:8b"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_from_email: str = ""
    password_reset_base_url: str = "http://localhost:5173/reset-password"
    app_env: str = "production"
    registration_mode: str = "restricted"
    AI_PROVIDER: str = ""
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_PROPOSAL_MODEL: str = ""
    GROQ_AGENT_MODEL: str = ""
    AI_TIMEOUT_SECONDS: float = 120.0
    AI_MAX_RETRIES: int = 1
    AI_RATE_LIMIT_PER_MINUTE: int = 10
    document_storage_root: Path = Path("backend/storage/document-requirements")

    @property
    def database_url(self) -> URL:
        """Build a safely encoded SQLAlchemy URL without logging credentials."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_database,
        )


def get_settings() -> Settings:
    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD must be set in the root .env file.")

    return Settings(
        postgres_host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "55732")),
        postgres_database=os.getenv("POSTGRES_DB", "fyphub_p1"),
        postgres_user=os.getenv("POSTGRES_USER", "fyphub_p1_user"),
        postgres_password=password,
        ollama_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_proposal_model=os.getenv("OLLAMA_PROPOSAL_MODEL", "llama3.1:8b"),
        ollama_agent_model=os.getenv("OLLAMA_AGENT_MODEL", "llama3.1:8b"),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=os.getenv("SMTP_FROM", os.getenv("SMTP_FROM_EMAIL", "")),
        smtp_from_email=os.getenv("SMTP_FROM_EMAIL", os.getenv("SMTP_FROM", "")),
        password_reset_base_url=os.getenv("PASSWORD_RESET_BASE_URL", "http://localhost:5173/reset-password").rstrip("/"),
        app_env=os.getenv("APP_ENV", "production").strip().lower(),
        registration_mode=os.getenv("REGISTRATION_MODE", "restricted"),
        AI_PROVIDER=os.getenv("AI_PROVIDER", "").strip().lower(),
        GROQ_API_KEY=os.getenv("GROQ_API_KEY", ""),
        GROQ_BASE_URL=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
        GROQ_PROPOSAL_MODEL=os.getenv("GROQ_PROPOSAL_MODEL", ""),
        GROQ_AGENT_MODEL=os.getenv("GROQ_AGENT_MODEL", ""),
        AI_TIMEOUT_SECONDS=float(os.getenv("AI_TIMEOUT_SECONDS", "120")),
        AI_MAX_RETRIES=min(2, max(0, int(os.getenv("AI_MAX_RETRIES", "1")))),
        AI_RATE_LIMIT_PER_MINUTE=max(1, int(os.getenv("AI_RATE_LIMIT_PER_MINUTE", "10"))),
        document_storage_root=Path(os.getenv("DOCUMENT_STORAGE_ROOT", str(Path(__file__).resolve().parents[1] / "storage" / "document-requirements"))).resolve(),
    )


settings = get_settings()
