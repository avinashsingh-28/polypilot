"""
Phase 5 Polygon API routes. All signed Polygon requests are made here on the backend; secrets
never leave the server. Writes that change Polygon require explicit confirmation fields.

NOTE: PolyPilot has no multi-user authentication yet (single local user). These endpoints are
intended for a locally running backend only — do not expose it publicly.
"""
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_user
from app.db.session import SessionLocal, get_db
from app.models.user import User
from app.models.polygon import PolygonItemState, PolygonOperation, PolygonSyncRun
from app.models.problem import Problem
from app.services.polygon import credentials as cred
from app.services.polygon import sync as S
from app.services.polygon.client import PolygonError

router = APIRouter(tags=["Polygon"])


# ── dependencies (overridable in tests) ───────────────────────────────────────
def get_polygon_transport() -> Optional[httpx.BaseTransport]:
    return None


def _background_executor(run_id: uuid.UUID, transport) -> None:
    def work():
        with SessionLocal() as db:
            run = db.get(PolygonSyncRun, run_id)
            problem = db.get(Problem, run.problem_id)
            integ = S.get_integration(db, problem)
            owner = db.get(User, problem.owner_id)
            try:
                with cred.make_client(db, owner, problem.id, run.id, transport) as client:
                    S.execute(db, run, problem, integ, client)
            except PolygonError as e:
                run.status, run.summary = "failed", f"{e.kind}: {e.message}"
                db.commit()
    threading.Thread(target=work, name=f"polygon-sync-{run_id}", daemon=True).start()


def get_sync_executor() -> Callable[[uuid.UUID, Any], None]:
    return _background_executor


def _err(e: Exception):
    if isinstance(e, S.SyncError):
        code = {"not_linked": 409, "duplicate": 409, "ambiguous": 409, "stale_plan": 409, "not_found": 404}.get(e.kind, 422)
        raise HTTPException(code, f"[{e.kind}] {e.message}")
    if isinstance(e, PolygonError):
        code = {"missing_credentials": 400, "configuration": 400, "not_found": 404}.get(e.kind, 502)
        raise HTTPException(code, f"[{e.kind}] {e.message}")
    if isinstance(e, ValueError):
        raise HTTPException(422, str(e))
    raise e


def _problem(db, pid) -> Problem:
    p = db.get(Problem, pid)
    if not p:
        raise HTTPException(404, "Problem not found")
    return p


def _linked(db, problem):
    try:
        return S.require_linked(S.get_integration(db, problem))
    except S.SyncError as e:
        _err(e)


def _confirm(integ, confirm_problem_id: str):
    if str(confirm_problem_id) != str(integ.external_problem_id):
        raise HTTPException(422, "confirm_problem_id must equal the linked Polygon problem id")


def _integ_out(integ) -> Optional[dict]:
    if not integ:
        return None
    return {k: getattr(integ, k) for k in (
        "id", "external_problem_id", "sync_status", "remote_name", "remote_owner", "access_type", "remote_revision",
        "working_copy_revision", "remote_modified", "link_mode", "pending_create", "last_remote_check_at",
        "last_synced_at", "last_commit", "last_build", "updated_at")}


def _run_out(r: PolygonSyncRun, ops: bool = False, db: Session = None) -> dict:
    d = {k: getattr(r, k) for k in ("id", "problem_id", "kind", "status", "scope", "summary", "result",
                                    "created_at", "started_at", "completed_at")}
    d["plan"] = r.plan
    if ops and db is not None:
        d["operations"] = [{k: getattr(o, k) for k in ("method", "write", "params", "status", "http_status",
                                                        "duration_ms", "response_summary", "error_kind",
                                                        "error_message", "created_at")}
                           for o in db.query(PolygonOperation).filter_by(sync_run_id=r.id)
                           .order_by(PolygonOperation.created_at).all()]
    return d


def _record(db, problem, integ, kind, status, summary, result=None) -> PolygonSyncRun:
    run = PolygonSyncRun(problem_id=problem.id, integration_id=integ.id if integ else None, kind=kind,
                         status=status, summary=summary, result=result, started_at=S._now(), completed_at=S._now())
    db.add(run)
    db.commit()
    return run


# ── account ──────────────────────────────────────────────────────────────────
class CredentialsIn(BaseModel):
    api_key: str = Field(..., min_length=8, max_length=200, pattern=r"^[A-Za-z0-9]+$")
    api_secret: str = Field(..., min_length=8, max_length=200, pattern=r"^[A-Za-z0-9]+$")


@router.get("/polygon/status")
def polygon_status(db: Session = Depends(get_db), user: User = Depends(require_user)):
    return cred.connection_status(db, user)


@router.put("/polygon/credentials")
def save_credentials(body: CredentialsIn, db: Session = Depends(get_db), user: User = Depends(require_user)):
    try:
        cred.store_credentials(db, user, body.api_key, body.api_secret)
    except PolygonError as e:
        _err(e)
    return cred.connection_status(db, user)   # never echoes the secret


@router.delete("/polygon/credentials")
def delete_credentials(db: Session = Depends(get_db), user: User = Depends(require_user)):
    cred.delete_stored(db, user)
    return cred.connection_status(db, user)


@router.post("/polygon/test")
def test_polygon_connection(db: Session = Depends(get_db), user: User = Depends(require_user), transport=Depends(get_polygon_transport)):
    try:
        res = cred.test_connection(db, user, transport)
    except PolygonError as e:
        res = {"ok": False, "kind": e.kind, "message": e.message, "accessible_problems": None}
    return {**res, "status": cred.connection_status(db, user)}


@router.get("/polygon/problems")
def list_polygon_problems(name: Optional[str] = Query(None, max_length=100), db: Session = Depends(get_db), user: User = Depends(require_user),
                          transport=Depends(get_polygon_transport)):
    try:
        with cred.make_client(db, user, transport=transport) as c:
            res = c.call("problems.list", {"name": name} if name else {}) or []
    except PolygonError as e:
        _err(e)
    keys = ("id", "name", "owner", "accessType", "revision", "workingCopyRevision", "modified", "deleted", "latestPackage")
    return [{k: p.get(k) for k in keys} for p in res if not p.get("deleted")]


# ── mapping ──────────────────────────────────────────────────────────────────
@router.get("/problems/{problem_id}/polygon")
def polygon_overview(problem_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)):
    problem = _problem(db, problem_id)
    integ = S.get_integration(db, problem)
    states = db.query(PolygonItemState).filter_by(integration_id=integ.id).all() if integ else []
    runs = (db.query(PolygonSyncRun).filter_by(problem_id=problem_id)
            .order_by(PolygonSyncRun.created_at.desc()).limit(20).all())
    return {"problem": {"id": problem.id, "title": problem.title, "slug": problem.slug,
                        "time_limit_seconds": float(problem.time_limit_seconds or 0),
                        "memory_limit_mb": problem.memory_limit_mb},
            "integration": _integ_out(integ),
            "item_states": [{k: getattr(s, k) for k in ("item_key", "item_type", "local_ref", "local_version",
                                                         "remote_name", "remote_index", "status", "error",
                                                         "uploaded_at")} for s in states],
            "runs": [{k: v for k, v in _run_out(r).items() if k not in ("plan", "result")} for r in runs]}


class CreateIn(BaseModel):
    name: str = Field(..., max_length=64)
    confirm: bool = False


@router.post("/problems/{problem_id}/polygon/create")
def create_remote(problem_id: uuid.UUID, body: CreateIn, db: Session = Depends(get_db), user: User = Depends(require_user),
                  transport=Depends(get_polygon_transport)):
    if not body.confirm:
        raise HTTPException(422, "Creating a Polygon problem requires confirm=true")
    problem = _problem(db, problem_id)
    try:
        with cred.make_client(db, user, problem.id, transport=transport) as c:
            integ = S.create_problem(db, problem, c, body.name)
    except (PolygonError, S.SyncError) as e:
        _record(db, problem, S.get_integration(db, problem), "create", "failed", f"{getattr(e, 'kind', '')}: {e.message}")
        _err(e)
    _record(db, problem, integ, "create", "completed", f"Created Polygon problem {integ.external_problem_id} ({integ.remote_name})")
    return _integ_out(integ)


@router.post("/problems/{problem_id}/polygon/reconcile-create")
def reconcile_create(problem_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user), transport=Depends(get_polygon_transport)):
    problem = _problem(db, problem_id)
    try:
        with cred.make_client(db, user, problem.id, transport=transport) as c:
            integ = S.reconcile_create(db, problem, c)
    except (PolygonError, S.SyncError) as e:
        _err(e)
    return _integ_out(integ)


class LinkIn(BaseModel):
    polygon_problem_id: str = Field(..., pattern=r"^\d{1,12}$")
    confirm_name: str = Field(..., max_length=100)


@router.post("/problems/{problem_id}/polygon/link")
def link_remote(problem_id: uuid.UUID, body: LinkIn, db: Session = Depends(get_db), user: User = Depends(require_user),
                transport=Depends(get_polygon_transport)):
    problem = _problem(db, problem_id)
    try:
        with cred.make_client(db, user, problem.id, transport=transport) as c:
            integ = S.link_problem(db, problem, c, body.polygon_problem_id, body.confirm_name)
    except (PolygonError, S.SyncError) as e:
        _err(e)
    _record(db, problem, integ, "link", "completed", f"Linked to Polygon problem {integ.external_problem_id}")
    return _integ_out(integ)


@router.post("/problems/{problem_id}/polygon/unlink")
def unlink_remote(problem_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)):
    problem = _problem(db, problem_id)
    integ = S.get_integration(db, problem)
    if integ:
        S.unlink(db, integ)
    return _integ_out(integ)


@router.post("/problems/{problem_id}/polygon/refresh")
def refresh_remote(problem_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user), transport=Depends(get_polygon_transport)):
    problem = _problem(db, problem_id)
    integ = _linked(db, problem)
    try:
        with cred.make_client(db, user, problem.id, transport=transport) as c:
            S.refresh(db, integ, c)
            info = c.call("problem.info", {"problemId": integ.external_problem_id})
            files = c.call("problem.files", {"problemId": integ.external_problem_id}) or {}
            sols = c.call("problem.solutions", {"problemId": integ.external_problem_id}) or []
            validator = c.call("problem.validator", {"problemId": integ.external_problem_id})
            checker = c.call("problem.checker", {"problemId": integ.external_problem_id})
            stmts = c.call("problem.statements", {"problemId": integ.external_problem_id}) or {}
    except (PolygonError, S.SyncError) as e:
        _err(e)
    return {"integration": _integ_out(integ), "info": info, "validator": validator, "checker": checker,
            "source_files": [f.get("name") for f in files.get("sourceFiles", [])],
            "resource_files": [f.get("name") for f in files.get("resourceFiles", [])],
            "solutions": [{"name": s.get("name"), "tag": s.get("tag")} for s in sols],
            "statement_languages": sorted(stmts.keys())}


# ── preview / dry run / sync ─────────────────────────────────────────────────
class ScopeIn(BaseModel):
    include: Optional[List[str]] = None
    solutions: Optional[List[str]] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    allow_unverified: List[str] = Field(default_factory=list)
    overwrite_remote: List[str] = Field(default_factory=list)


@router.post("/problems/{problem_id}/polygon/preview")
def preview(problem_id: uuid.UUID, scope: ScopeIn, db: Session = Depends(get_db), user: User = Depends(require_user)):
    """Local-only preview (no Polygon requests)."""
    problem = _problem(db, problem_id)
    try:
        return S.plan(db, problem, S.get_integration(db, problem), scope.model_dump(), None)
    except (S.SyncError, ValueError) as e:
        _err(e)


@router.post("/problems/{problem_id}/polygon/dry-run")
def dry_run(problem_id: uuid.UUID, scope: ScopeIn, db: Session = Depends(get_db), user: User = Depends(require_user),
            transport=Depends(get_polygon_transport)):
    """Reads remote state and computes the exact planned changes. Performs NO writes."""
    problem = _problem(db, problem_id)
    integ = _linked(db, problem)
    run = PolygonSyncRun(problem_id=problem.id, integration_id=integ.id, kind="dry_run", status="running",
                         scope=scope.model_dump(), started_at=S._now())
    db.add(run)
    db.commit()
    try:
        with cred.make_client(db, user, problem.id, run.id, transport) as c:
            p = S.plan(db, problem, integ, run.scope, c)
    except (PolygonError, S.SyncError, ValueError) as e:
        run.status, run.summary, run.completed_at = "failed", str(getattr(e, "message", e)), S._now()
        db.commit()
        _err(e)
    run.plan, run.status, run.completed_at = p, "completed", S._now()
    run.summary = ", ".join(f"{v} {k}" for k, v in sorted(p["counts"].items())) + " (dry run, nothing written)"
    db.commit()
    return _run_out(run)


class SyncIn(BaseModel):
    dry_run_id: uuid.UUID
    confirm_problem_id: str


@router.post("/problems/{problem_id}/polygon/sync", status_code=202)
def start_sync(problem_id: uuid.UUID, body: SyncIn, db: Session = Depends(get_db), user: User = Depends(require_user),
               transport=Depends(get_polygon_transport), executor=Depends(get_sync_executor)):
    """Upload the changes approved in a dry run into the Polygon working copy (no commit)."""
    problem = _problem(db, problem_id)
    integ = _linked(db, problem)
    _confirm(integ, body.confirm_problem_id)
    dr = db.query(PolygonSyncRun).filter_by(id=body.dry_run_id, problem_id=problem.id, kind="dry_run").first()
    if not dr or dr.status != "completed":
        raise HTTPException(404, "Completed dry run not found for this problem")
    if (S._now() - dr.completed_at.replace(tzinfo=dr.completed_at.tzinfo or S.timezone.utc)).total_seconds() > 3600:
        raise HTTPException(409, "Dry run is older than 1 hour; run a new one")
    active = db.query(PolygonSyncRun).filter(PolygonSyncRun.problem_id == problem.id, PolygonSyncRun.kind == "sync",
                                             PolygonSyncRun.status.in_(("planned", "running"))).first()
    if active:
        raise HTTPException(409, "A synchronization is already running for this problem")
    if not any(i["action"] in S.ACTIONABLE for i in (dr.plan or {}).get("items", [])):
        raise HTTPException(422, "The dry run contains no changes to upload")
    run = PolygonSyncRun(problem_id=problem.id, integration_id=integ.id, kind="sync", status="planned",
                         scope=dr.scope, plan=dr.plan, summary=f"Approved from dry run {dr.id}")
    db.add(run)
    db.commit()
    executor(run.id, transport)
    db.refresh(run)
    return _run_out(run)


@router.get("/problems/{problem_id}/polygon/runs")
def list_runs(problem_id: uuid.UUID, limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(require_user)):
    _problem(db, problem_id)
    runs = (db.query(PolygonSyncRun).filter_by(problem_id=problem_id)
            .order_by(PolygonSyncRun.created_at.desc()).limit(limit).all())
    return [{k: v for k, v in _run_out(r).items() if k != "plan"} for r in runs]


@router.get("/problems/{problem_id}/polygon/runs/{run_id}")
def get_run(problem_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)):
    r = db.query(PolygonSyncRun).filter_by(id=run_id, problem_id=problem_id).first()
    if not r:
        raise HTTPException(404, "Run not found")
    return _run_out(r, ops=True, db=db)


# ── working copy / commit / build ────────────────────────────────────────────
class ConfirmIn(BaseModel):
    confirm_problem_id: str
    confirm_text: Optional[str] = None


@router.post("/problems/{problem_id}/polygon/working-copy/update")
def wc_update(problem_id: uuid.UUID, body: ConfirmIn, db: Session = Depends(get_db), user: User = Depends(require_user),
              transport=Depends(get_polygon_transport)):
    problem = _problem(db, problem_id)
    integ = _linked(db, problem)
    _confirm(integ, body.confirm_problem_id)
    try:
        with cred.make_client(db, user, problem.id, transport=transport) as c:
            p = S.update_working_copy(db, integ, c)
    except (PolygonError, S.SyncError) as e:
        _err(e)
    _record(db, problem, integ, "working_copy", "completed", "Working copy updated to latest revision")
    return {"integration": _integ_out(integ), "remote_problem": p}


@router.post("/problems/{problem_id}/polygon/working-copy/discard")
def wc_discard(problem_id: uuid.UUID, body: ConfirmIn, db: Session = Depends(get_db), user: User = Depends(require_user),
               transport=Depends(get_polygon_transport)):
    problem = _problem(db, problem_id)
    integ = _linked(db, problem)
    _confirm(integ, body.confirm_problem_id)
    if body.confirm_text != "DISCARD":
        raise HTTPException(422, "Discarding the working copy loses uncommitted changes; send confirm_text='DISCARD'")
    try:
        with cred.make_client(db, user, problem.id, transport=transport) as c:
            p = S.discard_working_copy(db, integ, c)
    except (PolygonError, S.SyncError) as e:
        _err(e)
    _record(db, problem, integ, "working_copy", "completed", "Working copy discarded (uncommitted changes lost)")
    return {"integration": _integ_out(integ), "remote_problem": p}


class CommitIn(BaseModel):
    confirm_problem_id: str
    message: str = Field(..., min_length=3, max_length=500)
    minor_changes: bool = False


@router.post("/problems/{problem_id}/polygon/commit")
def commit(problem_id: uuid.UUID, body: CommitIn, db: Session = Depends(get_db), user: User = Depends(require_user),
           transport=Depends(get_polygon_transport)):
    problem = _problem(db, problem_id)
    integ = _linked(db, problem)
    _confirm(integ, body.confirm_problem_id)
    run = PolygonSyncRun(problem_id=problem.id, integration_id=integ.id, kind="commit", status="running",
                         scope={"message": body.message, "minor_changes": body.minor_changes}, started_at=S._now())
    db.add(run)
    db.commit()
    try:
        with cred.make_client(db, user, problem.id, run.id, transport) as c:
            out = S.commit(db, integ, c, body.message, body.minor_changes)
    except (PolygonError, S.SyncError) as e:
        run.status, run.summary, run.completed_at = "failed", f"{getattr(e, 'kind', '')}: {e.message}", S._now()
        db.commit()
        _err(e)
    run.result, run.completed_at = out, S._now()
    run.status = "completed" if out["confirmed"] else "unknown"
    run.summary = (f"Committed: revision {out['revision_before']} → {out['revision_after']}" if out["committed"]
                   else f"Not committed: {out.get('message')}")
    db.commit()
    return out


@router.get("/problems/{problem_id}/polygon/build/preflight")
def preflight(problem_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user), transport=Depends(get_polygon_transport)):
    problem = _problem(db, problem_id)
    integ = _linked(db, problem)
    try:
        with cred.make_client(db, user, problem.id, transport=transport) as c:
            return S.build_preflight(db, problem, integ, c)
    except (PolygonError, S.SyncError) as e:
        _err(e)


class BuildIn(BaseModel):
    confirm_problem_id: str
    full: bool = False
    verify: bool = True
    acknowledge_issues: bool = False


@router.post("/problems/{problem_id}/polygon/build")
def build(problem_id: uuid.UUID, body: BuildIn, db: Session = Depends(get_db), user: User = Depends(require_user),
          transport=Depends(get_polygon_transport)):
    problem = _problem(db, problem_id)
    integ = _linked(db, problem)
    _confirm(integ, body.confirm_problem_id)
    run = PolygonSyncRun(problem_id=problem.id, integration_id=integ.id, kind="build", status="running",
                         scope=body.model_dump(), started_at=S._now())
    db.add(run)
    db.commit()
    try:
        with cred.make_client(db, user, problem.id, run.id, transport) as c:
            pf = S.build_preflight(db, problem, integ, c)
            if pf["issues"] and not body.acknowledge_issues:
                run.status, run.summary, run.result, run.completed_at = "failed", "Preflight issues not acknowledged", pf, S._now()
                db.commit()
                raise HTTPException(409, "Package-readiness issues found; review them and resend with acknowledge_issues=true: "
                                    + "; ".join(pf["issues"])[:1500])
            out = S.build(db, integ, c, body.full, body.verify)
    except (PolygonError, S.SyncError) as e:
        run.status, run.summary, run.completed_at = "failed", f"{getattr(e, 'kind', '')}: {e.message}", S._now()
        db.commit()
        _err(e)
    run.result, run.completed_at = out, S._now()
    run.status = "completed" if out["state"] == "built" else ("failed" if out["state"] == "failed" else "running")
    run.summary = f"Build request {out['last_build'].get('request_status')}; package state: {out['state']}"
    db.commit()
    return out


@router.get("/problems/{problem_id}/polygon/build/status")
def build_status(problem_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user), transport=Depends(get_polygon_transport)):
    problem = _problem(db, problem_id)
    integ = _linked(db, problem)
    try:
        with cred.make_client(db, user, problem.id, transport=transport) as c:
            out = S.build_status(db, integ, c)
    except (PolygonError, S.SyncError) as e:
        _err(e)
    last = (db.query(PolygonSyncRun).filter_by(problem_id=problem.id, kind="build")
            .order_by(PolygonSyncRun.created_at.desc()).first())
    if last and last.status == "running" and out["state"] in ("built", "failed"):
        last.status = "completed" if out["state"] == "built" else "failed"
        last.summary, last.completed_at = f"Package state: {out['state']}", S._now()
        db.commit()
    return out
