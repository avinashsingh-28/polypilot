import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.api.deps import enforce_ownership, require_user
from app.api.routes.artifacts import router as artifacts_router
from app.api.routes.auth import router as auth_router
from app.api.routes.generation import router as generation_router
from app.api.routes.health import router as health_router
from app.api.routes.polygon import router as polygon_router
from app.api.routes.problems import router as problems_router
from app.api.routes.verification import router as verification_router
from app.api.routes.ai import router as ai_router
from app.core.config import get_settings
from app.core.observability import RequestContextMiddleware, configure_logging

settings = get_settings()
configure_logging(settings.LOG_LEVEL, settings.LOG_JSON)
log = logging.getLogger("polypilot")

if settings.is_production:
    problems = settings.production_problems()
    if problems:
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems))


def _recover_stale_generation_jobs() -> None:
    """Generation runs as an in-process background task; jobs interrupted by a restart would
    stay 'running' forever. Mark them failed on startup."""
    try:
        from app.db.session import SessionLocal
        from app.models.generation import GenerationJob
        from app.models.problem import Problem
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=10)
        with SessionLocal() as db:
            stale = db.query(GenerationJob).filter(GenerationJob.status == "running",
                                                   GenerationJob.started_at < cutoff).all()
            for job in stale:
                job.status, job.completed_at = "failed", datetime.now(timezone.utc)
                job.error_message = "Interrupted by a server restart; start generation again"
                p = db.get(Problem, job.problem_id)
                if p is not None and p.status == "generating":
                    p.status = "draft"
            db.commit()
            if stale:
                log.warning("marked %d interrupted generation jobs as failed", len(stale))
    except Exception:
        log.exception("startup recovery of generation jobs failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("backend starting", extra={"environment": settings.ENVIRONMENT, "version": settings.VERSION})
    if settings.STARTUP_RECOVERY:
        _recover_stale_generation_jobs()
    yield
    log.info("backend stopping")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend REST API for PolyPilot competitive programming problem-setting platform.",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in settings.CORS_ORIGINS if o != "*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestContextMiddleware, max_body=settings.MAX_REQUEST_BYTES)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc: RequestValidationError):
    # Field locations and messages only — never echo submitted values (could contain passwords).
    errors = [{"loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()]
    first = errors[0] if errors else {}
    return JSONResponse(status_code=422, content={
        "detail": f"Invalid request: {'.'.join(str(x) for x in (first.get('loc') or [])[1:])} {first.get('msg', '')}".strip(),
        "errors": errors})


@app.exception_handler(OperationalError)
async def database_unavailable(request, exc: OperationalError):
    # Connection refused / timeout / statement timeout: report a clean, retryable 503.
    log.error("database operation failed", extra={"path": request.url.path, "error": type(exc.orig).__name__})
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable. Please retry shortly."},
                        headers={"Retry-After": "5"})


app.include_router(health_router)

api_v1_router = APIRouter(prefix=settings.API_V1_PREFIX)
api_v1_router.include_router(auth_router)
protected = APIRouter(dependencies=[Depends(require_user), Depends(enforce_ownership)])
protected.include_router(problems_router)
protected.include_router(artifacts_router)
protected.include_router(generation_router)
protected.include_router(verification_router)
protected.include_router(polygon_router)
protected.include_router(ai_router)
api_v1_router.include_router(protected)

app.include_router(api_v1_router)
