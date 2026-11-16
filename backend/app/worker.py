"""
PolyPilot verification worker (separate process from the FastAPI server).

    python -m app.worker            # poll forever
    python -m app.worker --once     # process at most one queued run, then exit
    python -m app.worker --check    # report sandbox status and harness self-check

The worker claims queued verification runs from PostgreSQL
(SELECT ... FOR UPDATE SKIP LOCKED), executes them through the Docker sandbox,
and writes results back. It exposes no network interface.
"""
import argparse
import json
import logging
import os
import socket
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.user import WorkerHeartbeat
from app.models.verification import VerificationRun
from app.services.sandbox import get_sandbox
from app.services.verification.engine import execute_run

logger = logging.getLogger("polypilot.worker")
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def _now():
    return datetime.now(timezone.utc)


def claim_next(db: Session) -> Optional[VerificationRun]:
    stmt = select(VerificationRun).where(VerificationRun.status == "queued") \
        .order_by(VerificationRun.created_at).limit(1)
    if db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)
    run = db.execute(stmt).scalars().first()
    if run is None:
        db.rollback()
        return None
    if run.cancel_requested:
        run.status, run.summary, run.completed_at = "cancelled", "Cancelled before start", _now()
        db.commit()
        return None
    run.status, run.worker_id = "running", WORKER_ID
    run.started_at = run.heartbeat_at = _now()
    db.commit()
    return run


def recover_stale(db: Session, stale_after: int) -> int:
    cutoff = _now() - timedelta(seconds=stale_after)
    stale = db.query(VerificationRun).filter(VerificationRun.status == "running",
                                             VerificationRun.heartbeat_at < cutoff).all()
    for r in stale:
        r.status, r.completed_at = "failed", _now()
        r.summary = "Worker stopped unexpectedly (no heartbeat)"
        r.report = {**(r.report or {}), "failure_kind": "infrastructure"}
    db.commit()
    return len(stale)


_sandbox_ok = False


def beat(state: str, run_id: Optional[str] = None, finished: Optional[str] = None) -> None:
    """Upsert this worker's heartbeat row (used by /health/worker)."""
    try:
        with SessionLocal() as db:
            hb = db.get(WorkerHeartbeat, WORKER_ID)
            if hb is None:
                hb = WorkerHeartbeat(worker_id=WORKER_ID, started_at=_now(), jobs_completed=0, jobs_failed=0)
                db.add(hb)
            hb.last_seen_at, hb.state, hb.current_run_id = _now(), state, run_id
            hb.sandbox_available = _sandbox_ok
            if finished == "passed":
                hb.jobs_completed = (hb.jobs_completed or 0) + 1
            elif finished:
                hb.jobs_failed = (hb.jobs_failed or 0) + 1
            db.commit()
    except Exception:
        logger.exception("heartbeat failed (database unavailable?)")


def process_one() -> bool:
    with SessionLocal() as db:
        run = claim_next(db)
        if run is None:
            return False
        logger.info("Running %s %s for problem %s", run.test_type, run.id, run.problem_id)
        beat("busy", str(run.id))
        execute_run(db, run)
        logger.info("Run %s finished: %s — %s", run.id, run.status, run.summary)
        beat("idle", finished=run.status)
        return True


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="PolyPilot verification worker")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    settings = get_settings()
    sb = get_sandbox()

    if args.check:
        st = sb.status()
        print(json.dumps(st, indent=2))
        if st["available"]:
            print(json.dumps(sb.self_check(), indent=2))
        return 0 if st["available"] else 1

    global _sandbox_ok
    st = sb.status()
    _sandbox_ok = bool(st["available"])
    if not st["available"]:
        logger.error("Sandbox unavailable: %s. Runs will fail with an infrastructure error until Docker "
                     "and the image are available. Nothing will execute on the host.", st)
    else:
        removed = sb.cleanup_orphans()
        if removed:
            logger.warning("Removed %d orphaned sandbox containers", removed)
    with SessionLocal() as db:
        n = recover_stale(db, settings.WORKER_STALE_AFTER_SEC)
        if n:
            logger.warning("Marked %d stale running jobs as failed", n)

    logger.info("Worker %s started (sandbox mode=%s)", WORKER_ID, st["mode"])
    last_beat = 0.0
    while True:
        if time.monotonic() - last_beat > 15:
            beat("idle")
            last_beat = time.monotonic()
        try:
            worked = process_one()
            if worked:
                last_beat = time.monotonic()
        except KeyboardInterrupt:
            beat("stopping")
            return 0
        except Exception:
            logger.exception("Worker loop error")
            worked = False
        if args.once:
            return 0
        if not worked:
            time.sleep(settings.WORKER_POLL_INTERVAL_SEC)


if __name__ == "__main__":
    sys.exit(main())
