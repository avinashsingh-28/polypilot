"""
Phase 4 verification API.

This API never compiles or executes code. It only creates/reads database rows;
the separate worker process (python -m app.worker) executes queued runs in the
Docker sandbox. There is no endpoint that accepts arbitrary commands.

GET    /problems/{id}/verification/summary
GET    /sandbox/status
POST   /problems/{id}/verification-runs
GET    /problems/{id}/verification-runs
GET    /problems/{id}/verification-runs/{run_id}
POST   /problems/{id}/verification-runs/{run_id}/cancel
GET    /problems/{id}/test-cases            POST  (manual / upload / invalid)
POST   /problems/{id}/test-cases/import-samples
GET    /problems/{id}/test-cases/{tc_id}    DELETE
GET    /problems/{id}/counterexamples       GET /{cx_id}
GET    /problems/{id}/repairs               POST (AI proposal)
POST   /problems/{id}/repairs/{rid}/accept  POST /{rid}/reject
"""
import hashlib
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.artifact import ProblemArtifact
from app.models.counterexample import Counterexample
from app.models.problem import Problem
from app.models.user import User
from app.api.deps import require_user
from app.models.solution_repair import SolutionRepair
from app.models.test_case import TestCase
from app.models.verification import VerificationRun
from app.schemas.verification import (
    CounterexampleResponse, RepairCreate, RepairResponse, SandboxStatus, TestCaseCreate, TestCaseDetail,
    TestCaseResponse, VerificationRunCreate, VerificationRunDetail, VerificationRunResponse, VerificationSummary,
)
from app.services.verification.config import TEST_TYPES, ConfigError, effective_config

router = APIRouter(tags=["Verification"])
ACTIVE = ("pending", "queued", "running")
PREVIEW = 2000


def _now():
    return datetime.now(timezone.utc)


def _problem(db: Session, problem_id: uuid.UUID) -> Problem:
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, f"Problem {problem_id} not found")
    return p


def _scoped(db: Session, model, obj_id: uuid.UUID, problem_id: uuid.UUID, what: str):
    obj = db.query(model).filter(model.id == obj_id, model.problem_id == problem_id).first()
    if not obj:
        raise HTTPException(404, f"{what} not found for this problem")
    return obj


# ── Sandbox status (cached; runs only `docker version` / `image inspect`) ─────
_sandbox_cache = {"t": 0.0, "v": None}
_sandbox_lock = threading.Lock()


@router.get("/sandbox/status", response_model=SandboxStatus)
def sandbox_status():
    with _sandbox_lock:
        if _sandbox_cache["v"] is None or time.monotonic() - _sandbox_cache["t"] > 30:
            from app.services.sandbox import get_sandbox
            _sandbox_cache["v"] = get_sandbox().status()
            _sandbox_cache["t"] = time.monotonic()
        return _sandbox_cache["v"]


# ── Verification runs ─────────────────────────────────────────────────────────
@router.post("/problems/{problem_id}/verification-runs", response_model=VerificationRunResponse, status_code=202)
def create_run(problem_id: uuid.UUID, body: VerificationRunCreate, db: Session = Depends(get_db)):
    problem = _problem(db, problem_id)
    s = get_settings()
    if body.idempotency_key:
        existing = db.query(VerificationRun).filter_by(problem_id=problem_id,
                                                       idempotency_key=body.idempotency_key).first()
        if existing:
            return existing
    try:
        cfg = effective_config(body.test_type, body.config, problem, s)
    except ConfigError as exc:
        raise HTTPException(422, str(exc))
    _check_refs(db, problem_id, cfg)
    active = db.query(func.count(VerificationRun.id)).filter(
        VerificationRun.problem_id == problem_id, VerificationRun.status.in_(ACTIVE)).scalar()
    if active >= s.MAX_ACTIVE_RUNS_PER_PROBLEM:
        raise HTTPException(429, f"This problem already has {active} active verification runs "
                                 f"(max {s.MAX_ACTIVE_RUNS_PER_PROBLEM}). Wait or cancel one.")
    user_active = (db.query(func.count(VerificationRun.id)).join(Problem, Problem.id == VerificationRun.problem_id)
                   .filter(Problem.owner_id == problem.owner_id, VerificationRun.status.in_(ACTIVE)).scalar())
    if user_active >= s.MAX_ACTIVE_RUNS_PER_USER:
        raise HTTPException(429, f"You already have {user_active} active verification runs "
                                 f"(max {s.MAX_ACTIVE_RUNS_PER_USER}). Wait or cancel one.")
    queued = db.query(func.count(VerificationRun.id)).filter(VerificationRun.status == "queued").scalar()
    if queued >= s.MAX_QUEUED_RUNS_TOTAL:
        raise HTTPException(503, "The verification queue is full. Please try again in a few minutes.")
    run = VerificationRun(problem_id=problem_id, test_type=body.test_type, status="queued",
                          config_params=cfg, idempotency_key=body.idempotency_key,
                          progress={"iterations_done": 0}, summary="Queued — waiting for worker")
    db.add(run)
    try:
        db.commit()
    except IntegrityError:  # concurrent retry with the same idempotency key
        db.rollback()
        return db.query(VerificationRun).filter_by(problem_id=problem_id,
                                                   idempotency_key=body.idempotency_key).one()
    db.refresh(run)
    return run


def _check_refs(db: Session, problem_id: uuid.UUID, cfg: dict) -> None:
    """Reject references to artifacts/repairs/counterexamples of another problem up front."""
    for key in ("target", "reference", "candidate"):
        spec = cfg.get(key) or {}
        for field, model in (("artifact_id", ProblemArtifact), ("repair_id", SolutionRepair)):
            if spec.get(field):
                try:
                    oid = uuid.UUID(spec[field])
                except ValueError:
                    raise HTTPException(422, f"Invalid {field}")
                _scoped(db, model, oid, problem_id, field)
    if cfg.get("counterexample_id"):
        _scoped(db, Counterexample, uuid.UUID(cfg["counterexample_id"]), problem_id, "Counterexample")


@router.get("/verification-runs")
def list_my_runs(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                 test_type: Optional[str] = None, db: Session = Depends(get_db),
                 user: User = Depends(require_user)):
    """Verification history across all of the current user's problems (newest first)."""
    q = (db.query(VerificationRun, Problem.title)
         .join(Problem, Problem.id == VerificationRun.problem_id)
         .filter(Problem.owner_id == user.id))
    if test_type:
        q = q.filter(VerificationRun.test_type == test_type)
    total = q.count()
    rows = q.order_by(VerificationRun.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [
        {"id": r.id, "problem_id": r.problem_id, "problem_title": title, "test_type": r.test_type, "status": r.status,
         "summary": r.summary, "created_at": r.created_at, "started_at": r.started_at, "completed_at": r.completed_at,
         "progress": r.progress}
        for r, title in rows]}


@router.get("/problems/{problem_id}/verification-runs", response_model=List[VerificationRunResponse])
def list_runs(problem_id: uuid.UUID, test_type: Optional[str] = None, limit: int = Query(30, ge=1, le=100),
              db: Session = Depends(get_db)):
    _problem(db, problem_id)
    q = db.query(VerificationRun).filter(VerificationRun.problem_id == problem_id)
    if test_type:
        q = q.filter(VerificationRun.test_type == test_type)
    return q.order_by(VerificationRun.created_at.desc()).limit(limit).all()


@router.get("/problems/{problem_id}/verification-runs/{run_id}", response_model=VerificationRunDetail)
def get_run(problem_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db)):
    return _scoped(db, VerificationRun, run_id, problem_id, "Verification run")


@router.post("/problems/{problem_id}/verification-runs/{run_id}/cancel", response_model=VerificationRunResponse)
def cancel_run(problem_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = _scoped(db, VerificationRun, run_id, problem_id, "Verification run")
    if run.status in ("pending", "queued"):
        run.status, run.summary, run.completed_at = "cancelled", "Cancelled before start", _now()
    elif run.status == "running":
        run.summary = "Cancellation requested — stopping after the current batch"
    run.cancel_requested = True
    db.commit()
    db.refresh(run)
    return run


def _ai_ok(db: Session, problem_id) -> bool:
    from app.services.ai import ai_available
    p = db.get(Problem, problem_id)
    return ai_available(db, p.owner_id if p else None, get_settings())


@router.get("/problems/{problem_id}/verification/summary", response_model=VerificationSummary)
def summary(problem_id: uuid.UUID, db: Session = Depends(get_db)):
    _problem(db, problem_id)
    latest = {}
    for t in TEST_TYPES:
        latest[t] = (db.query(VerificationRun).filter_by(problem_id=problem_id, test_type=t)
                     .order_by(VerificationRun.created_at.desc()).first())
    active = (db.query(VerificationRun).filter(VerificationRun.problem_id == problem_id,
                                               VerificationRun.status.in_(ACTIVE))
              .order_by(VerificationRun.created_at.desc()).all())
    counts = dict(db.query(TestCase.validation_status, func.count(TestCase.id))
                  .filter(TestCase.problem_id == problem_id).group_by(TestCase.validation_status).all())
    counts["total"] = sum(counts.values())
    cx = db.query(func.count(Counterexample.id)).filter(Counterexample.problem_id == problem_id).scalar()
    return {"latest_by_type": latest, "active_runs": active, "test_case_counts": counts,
            "counterexample_count": cx, "ai_configured": _ai_ok(db, problem_id)}


# ── Test cases ────────────────────────────────────────────────────────────────
def _tc_out(tc: TestCase, detail: bool = False) -> dict:
    d = {c: getattr(tc, c) for c in ("id", "problem_id", "test_type", "is_valid", "validation_status",
                                     "validation_feedback", "generator_cmd", "generation_meta", "created_at")}
    d.update(input_preview=tc.input_data[:PREVIEW], input_bytes=tc.input_bytes or len(tc.input_data.encode()),
             input_truncated=len(tc.input_data) > PREVIEW, has_expected_output=tc.expected_output is not None)
    if detail:
        d.update(input_data=tc.input_data, expected_output=tc.expected_output)
    return d


def _clean_text(s: str, what: str) -> str:
    lim = get_settings().MAX_INPUT_BYTES
    if len(s.encode("utf-8")) > lim:
        raise HTTPException(413, f"{what} exceeds the {lim}-byte limit")
    if "\x00" in s:
        raise HTTPException(422, f"{what} contains NUL bytes; only text test data is supported")
    return s.replace("\r\n", "\n")


@router.get("/problems/{problem_id}/test-cases", response_model=List[TestCaseResponse])
def list_test_cases(problem_id: uuid.UUID, limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db)):
    _problem(db, problem_id)
    rows = (db.query(TestCase).filter(TestCase.problem_id == problem_id)
            .order_by(TestCase.created_at).offset(offset).limit(limit).all())
    return [_tc_out(t) for t in rows]


@router.post("/problems/{problem_id}/test-cases", response_model=TestCaseDetail, status_code=201)
def create_test_case(problem_id: uuid.UUID, body: TestCaseCreate, db: Session = Depends(get_db)):
    _problem(db, problem_id)
    inp = _clean_text(body.input_data, "Input")
    exp = _clean_text(body.expected_output, "Expected output") if body.expected_output not in (None, "") else None
    meta = {"filename": body.filename.replace("\\", "/").split("/")[-1][:100]} if body.filename else None
    tc = TestCase(problem_id=problem_id, test_type=body.test_type, input_data=inp, expected_output=exp,
                  is_valid=False, validation_status="unchecked", input_bytes=len(inp.encode()),
                  generation_meta=meta)
    db.add(tc)
    db.commit()
    db.refresh(tc)
    return _tc_out(tc, True)


@router.post("/problems/{problem_id}/test-cases/import-samples", response_model=List[TestCaseResponse])
def import_samples(problem_id: uuid.UUID, db: Session = Depends(get_db)):
    _problem(db, problem_id)
    art = db.query(ProblemArtifact).filter_by(problem_id=problem_id, artifact_type="specification").first()
    if not art:
        raise HTTPException(404, "No specification artifact; generate the problem first")
    try:
        spec = json.loads(art.content)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(422, "Specification artifact is not valid JSON")
    samples = spec.get("samples") if isinstance(spec, dict) else None
    if not isinstance(samples, list) or not samples:
        raise HTTPException(422, "Specification contains no samples")
    have = {hashlib.sha256(t.input_data.encode()).hexdigest()
            for t in db.query(TestCase).filter_by(problem_id=problem_id, test_type="sample")}
    created = []
    for i, smp in enumerate(samples[:20]):
        if not isinstance(smp, dict) or not isinstance(smp.get("input"), str):
            continue
        inp = _clean_text(smp["input"], "Sample input")
        if not inp.endswith("\n"):
            inp += "\n"
        if hashlib.sha256(inp.encode()).hexdigest() in have:
            continue
        out = smp.get("output")
        tc = TestCase(problem_id=problem_id, test_type="sample", input_data=inp,
                      expected_output=_clean_text(out, "Sample output") if isinstance(out, str) else None,
                      is_valid=False, validation_status="unchecked", input_bytes=len(inp.encode()),
                      generation_meta={"sample_index": i, "source": "specification"})
        db.add(tc)
        created.append(tc)
    db.commit()
    return [_tc_out(t) for t in created]


@router.get("/problems/{problem_id}/test-cases/{tc_id}", response_model=TestCaseDetail)
def get_test_case(problem_id: uuid.UUID, tc_id: uuid.UUID, db: Session = Depends(get_db)):
    return _tc_out(_scoped(db, TestCase, tc_id, problem_id, "Test case"), True)


@router.delete("/problems/{problem_id}/test-cases/{tc_id}", status_code=204)
def delete_test_case(problem_id: uuid.UUID, tc_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.models.polygon import PolygonItemState
    db.delete(_scoped(db, TestCase, tc_id, problem_id, "Test case"))
    # Forget local sync tracking for this test (the remote Polygon test is never deleted automatically).
    db.query(PolygonItemState).filter_by(problem_id=problem_id, item_key=f"test:{tc_id}").delete()
    db.commit()


# ── Counterexamples ───────────────────────────────────────────────────────────
@router.get("/problems/{problem_id}/counterexamples", response_model=List[CounterexampleResponse])
def list_counterexamples(problem_id: uuid.UUID, run_id: Optional[uuid.UUID] = None,
                         limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    _problem(db, problem_id)
    q = db.query(Counterexample).filter(Counterexample.problem_id == problem_id)
    if run_id:
        q = q.filter(Counterexample.verification_run_id == run_id)
    return q.order_by(Counterexample.created_at.desc()).limit(limit).all()


@router.get("/problems/{problem_id}/counterexamples/{cx_id}", response_model=CounterexampleResponse)
def get_counterexample(problem_id: uuid.UUID, cx_id: uuid.UUID, db: Session = Depends(get_db)):
    return _scoped(db, Counterexample, cx_id, problem_id, "Counterexample")


# ── AI repair ─────────────────────────────────────────────────────────────────
@router.get("/problems/{problem_id}/repairs", response_model=List[RepairResponse])
def list_repairs(problem_id: uuid.UUID, db: Session = Depends(get_db)):
    _problem(db, problem_id)
    return (db.query(SolutionRepair).filter(SolutionRepair.problem_id == problem_id)
            .order_by(SolutionRepair.created_at.desc()).limit(50).all())


@router.post("/problems/{problem_id}/repairs", response_model=RepairResponse, status_code=201)
async def create_repair(problem_id: uuid.UUID, body: RepairCreate, db: Session = Depends(get_db)):
    from app.services.ai import resolve_provider
    from app.services.verification.repair import RepairError, propose_repair

    problem = _problem(db, problem_id)
    cx = _scoped(db, Counterexample, body.counterexample_id, problem_id, "Counterexample")
    settings = get_settings()
    if body.source and len(body.source.encode()) > settings.MAX_SOURCE_BYTES:
        raise HTTPException(413, "Source too large")
    from app.services.ai import TrackedProvider
    from app.services.ai.base import AIError
    try:
        inner, limit = resolve_provider(db, problem.owner_id, settings)
        ai = TrackedProvider(inner, lambda: db, problem.owner_id, problem.id, "repair", limit)
        return await propose_repair(db, ai, problem, cx,
                                    str(body.artifact_id) if body.artifact_id else None,
                                    body.source, body.language)
    except RepairError as exc:
        raise HTTPException(422, str(exc))
    except AIError as exc:
        raise HTTPException(429 if exc.kind in ("quota_exceeded", "rate_limited")
                            else 503 if exc.kind in ("missing_key", "configuration") else 502,
                            f"AI provider error [{exc.kind}]: {exc.message}")


@router.post("/problems/{problem_id}/repairs/{repair_id}/accept", response_model=RepairResponse)
def accept_repair(problem_id: uuid.UUID, repair_id: uuid.UUID, db: Session = Depends(get_db)):
    """Accept = queue a sandboxed re-test (failing input + regression suite). Artifacts are not modified."""
    problem = _problem(db, problem_id)
    rep = _scoped(db, SolutionRepair, repair_id, problem_id, "Repair")
    if rep.status == "rejected":
        raise HTTPException(409, "Repair was rejected")
    if rep.retest_run_id is None:
        raw = {"candidate": {"repair_id": str(rep.id)}, "expected_verdict": "AC"}
        if rep.counterexample_id:
            raw["counterexample_id"] = str(rep.counterexample_id)
        cfg = effective_config("candidate", raw, problem, get_settings())
        run = VerificationRun(problem_id=problem_id, test_type="candidate", status="queued", config_params=cfg,
                              idempotency_key=f"repair-{rep.id}", progress={"iterations_done": 0},
                              summary="Queued — re-testing accepted repair")
        db.add(run)
        db.flush()
        rep.retest_run_id = run.id
    rep.status = "accepted"
    db.commit()
    db.refresh(rep)
    return rep


@router.post("/problems/{problem_id}/repairs/{repair_id}/reject", response_model=RepairResponse)
def reject_repair(problem_id: uuid.UUID, repair_id: uuid.UUID, db: Session = Depends(get_db)):
    rep = _scoped(db, SolutionRepair, repair_id, problem_id, "Repair")
    if rep.status == "accepted":
        raise HTTPException(409, "Repair was already accepted")
    rep.status = "rejected"
    db.commit()
    db.refresh(rep)
    return rep
