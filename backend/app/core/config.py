from functools import lru_cache
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Project metadata
    PROJECT_NAME: str = "PolyPilot Backend"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # PostgreSQL connection settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "polypilot"
    POSTGRES_USER: str = "polypilot_user"
    POSTGRES_PASSWORD: str = ""
    DATABASE_URL: Optional[str] = None

    # CORS origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000"
    ]

    @property
    def sync_database_url(self) -> str:
        if self.DATABASE_URL:
            # Ensure using psycopg 3 driver prefix if generic postgresql:// was supplied
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
            return self.DATABASE_URL
        
        # Build URL from components
        user = self.POSTGRES_USER
        password = self.POSTGRES_PASSWORD
        host = self.POSTGRES_HOST
        port = self.POSTGRES_PORT
        db = self.POSTGRES_DB
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
