"""
Health & metrics.

/health           liveness (process is up; no dependencies checked)
/health/ready     readiness: database reachable (503 otherwise)
/health/db        database check with latency (no error details exposed)
/health/worker    verification worker freshness from its DB heartbeat (503 if none is alive)
/metrics          Prometheus text; requires METRICS_TOKEN bearer if configured, otherwise
                  only served outside production
"""
import hmac
import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.observability import metrics
from app.db.session import get_db
from app.models.user import WorkerHeartbeat
from app.models.verification import VerificationRun
from app.schemas.health import DbHealthResponse, HealthResponse

router = APIRouter(tags=["Health"])
settings = get_settings()
log = logging.getLogger("polypilot.health")


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.VERSION, environment=settings.ENVIRONMENT)


def _db_ok(db: Session):
    start = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        return True, round((time.perf_counter() - start) * 1000, 2)
    except Exception:
        log.exception("database health check failed")
        return False, None


@router.get("/health/db", response_model=DbHealthResponse)
def get_db_health(response: Response, db: Session = Depends(get_db)) -> DbHealthResponse:
    ok, latency = _db_ok(db)
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return DbHealthResponse(status="error", database="postgresql", reachable=False, detail="Database unreachable")
    return DbHealthResponse(status="ok", database="postgresql", reachable=True, latency_ms=latency)


@router.get("/health/ready")
def ready(response: Response, db: Session = Depends(get_db)):
    ok, latency = _db_ok(db)
    if not ok:
        response.status_code = 503
    return {"status": "ready" if ok else "not_ready", "database": ok, "db_latency_ms": latency}


def worker_snapshot(db: Session) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.WORKER_HEARTBEAT_STALE_SEC)
    rows = db.query(WorkerHeartbeat).all()
    alive = [w for w in rows if (w.last_seen_at if w.last_seen_at.tzinfo else w.last_seen_at.replace(tzinfo=timezone.utc)) >= cutoff]
    return {"workers_alive": len(alive), "workers_busy": sum(1 for w in alive if w.state == "busy"),
            "sandbox_available": any(w.sandbox_available for w in alive),
            "last_seen_at": max((w.last_seen_at for w in rows), default=None)}


@router.get("/health/worker")
def worker_health(response: Response, db: Session = Depends(get_db)):
    snap = worker_snapshot(db)
    queued = db.query(func.count(VerificationRun.id)).filter(VerificationRun.status == "queued").scalar()
    ok = snap["workers_alive"] > 0
    if not ok:
        response.status_code = 503
    return {"status": "ok" if ok else "no_live_worker", **snap, "queued_runs": queued}


@router.get("/metrics", response_class=PlainTextResponse)
def get_metrics(request: Request, db: Session = Depends(get_db)):
    if settings.METRICS_TOKEN:
        presented = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not hmac.compare_digest(presented, settings.METRICS_TOKEN):
            raise HTTPException(401, "Unauthorized")
    elif settings.is_production:
        raise HTTPException(404, "Not found")
    snap = worker_snapshot(db)
    by_status = dict(db.query(VerificationRun.status, func.count(VerificationRun.id))
                     .group_by(VerificationRun.status).all())
    gauges = {"workers_alive": snap["workers_alive"], "workers_busy": snap["workers_busy"]}
    for st in ("queued", "running", "passed", "failed", "cancelled"):
        gauges[f'verification_runs{{status="{st}"}}'] = by_status.get(st, 0)
    return metrics.render(gauges)
