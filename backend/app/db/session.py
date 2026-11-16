from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import get_settings

settings = get_settings()

_connect_args = {}
if settings.sync_database_url.startswith("postgresql"):
    _connect_args = {
        "connect_timeout": settings.DB_CONNECT_TIMEOUT_SEC,
        # Server-side guard against runaway queries.
        "options": f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}",
        "application_name": "polypilot",
    }

engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT_SEC,
    pool_recycle=1800,
    connect_args=_connect_args,
    echo=False
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
