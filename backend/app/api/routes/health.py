import time
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.health import HealthResponse, DbHealthResponse

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Basic health check indicating the FastAPI application is alive."""
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT
    )


@router.get("/health/db", response_model=DbHealthResponse)
def get_db_health(response: Response, db: Session = Depends(get_db)) -> DbHealthResponse:
    """
    Executes a lightweight query against PostgreSQL to verify connectivity.
    Returns HTTP 503 if unreachable, HTTP 200 if reachable.
    """
    start_time = time.perf_counter()
    try:
        db.execute(text("SELECT 1;"))
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return DbHealthResponse(
            status="ok",
            database="postgresql",
            reachable=True,
            latency_ms=latency_ms
        )
    except Exception as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return DbHealthResponse(
            status="error",
            database="postgresql",
            reachable=False,
            detail=str(e)
        )
