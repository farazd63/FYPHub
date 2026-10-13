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
    )


settings = get_settings()
