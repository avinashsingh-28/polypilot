import sys
import os
from typing import Generator
import pytest

# Tests must never touch the real database from app startup hooks.
os.environ["STARTUP_RECOVERY"] = "false"

# Ensure backend root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Create in-memory SQLite engine for fast, completely isolated tests
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


TEST_EMAIL = "tester@example.com"
TEST_PASSWORD = "correct-horse-battery-9"


def login_client(test_client: TestClient, email: str = TEST_EMAIL, password: str = TEST_PASSWORD) -> None:
    """Register (idempotent) + login, then send the CSRF header on every request like the frontend does."""
    test_client.post("/api/v1/auth/register", json={"email": email, "password": password})
    r = test_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    test_client.headers["X-CSRF-Token"] = test_client.cookies.get("pp_csrf")


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.core.security import limiter
    limiter.clear()
    yield


@pytest.fixture
def anon_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client(anon_client: TestClient) -> TestClient:
    login_client(anon_client)
    return anon_client


@pytest.fixture
def auth_user(client, db_session):
    from app.models.user import User
    return db_session.query(User).filter_by(email=TEST_EMAIL).one()
