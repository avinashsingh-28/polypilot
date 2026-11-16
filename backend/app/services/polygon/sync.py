"""
Polygon synchronization engine.

Flow: plan (reads only) → user reviews dry run → execute (writes into the caller's Polygon
working copy; never commits) → read back → user explicitly commits → user explicitly builds.

Safety:
  * Writes are never retried blindly; ambiguous results are reconciled with read methods.
  * Remote files we did not upload (or that changed remotely since our upload) are conflicts
    and are never overwritten unless the user lists the item in scope.overwrite_remote.
  * Remote tests are only added (checkExisting=true) or edited at indices we uploaded whose
    remote content is still what we uploaded. Remote tests are never deleted.
  * Working-copy discard / update, commit and build are separate explicit actions.
"""
import base64
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.integration import ProblemIntegration
from app.models.polygon import PolygonItemState, PolygonSyncRun
from app.models.problem import Problem
from app.models.verification import VerificationRun
from app.services.polygon.client import PolygonClient, PolygonError
from app.services.polygon.mapping import LocalItem, build_local_items, norm, sha

logger = logging.getLogger(__name__)
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ACTIONABLE = ("create", "update")
ORDER = {"info": 0, "file": 1, "solution": 2, "assign": 3, "statement": 4, "tutorial": 5, "test": 6}


def _now():
    return datetime.now(timezone.utc)


class SyncError(Exception):
    def __init__(self, message: str, kind: str = "invalid_request"):
        super().__init__(message)
        self.message, self.kind = message, kind


# ── integration helpers ───────────────────────────────────────────────────────
def get_integration(db: Session, problem: Problem, create: bool = False) -> Optional[ProblemIntegration]:
    integ = db.query(ProblemIntegration).filter_by(problem_id=problem.id, platform_name="polygon").first()
    if integ is None and create:
        integ = ProblemIntegration(problem_id=problem.id, platform_name="polygon", sync_status="unlinked")
        db.add(integ)
        db.flush()
    return integ


def require_linked(integ: Optional[ProblemIntegration]) -> ProblemIntegration:
    if not integ or not integ.external_problem_id or integ.sync_status in ("unlinked", "creating", "create_unknown"):
        raise SyncError("This problem is not linked to a Polygon problem", "not_linked")
    return integ


def _apply_remote_problem(integ: ProblemIntegration, p: dict) -> None:
    integ.remote_name = p.get("name")
    integ.remote_owner = p.get("owner")
    integ.access_type = p.get("accessType")
    integ.remote_revision = p.get("revision")
    integ.working_copy_revision = p.get("workingCopyRevision")
    integ.remote_modified = p.get("modified")
    integ.last_remote_check_at = _now()


def fetch_remote_problem(client: PolygonClient, polygon_id: str) -> dict:
    res = client.call("problems.list", {"id": polygon_id}) or []
    match = [p for p in res if str(p.get("id")) == str(polygon_id)]
    if not match:
        raise SyncError(f"Polygon problem {polygon_id} is not accessible with these credentials", "not_found")
    return match[0]


def refresh(db: Session, integ: ProblemIntegration, client: PolygonClient) -> dict:
    p = fetch_remote_problem(client, integ.external_problem_id)
    _apply_remote_problem(integ, p)
    db.commit()
    return p


# ── create / link ─────────────────────────────────────────────────────────────
def create_problem(db: Session, problem: Problem, client: PolygonClient, name: str) -> ProblemIntegration:
    if not NAME_RE.match(name or ""):
        raise SyncError("Polygon problem name must be 1–64 lowercase letters, digits or dashes, starting with a "
                        "letter or digit (local rule; Polygon may apply further checks)")
    integ = get_integration(db, problem, create=True)
    if integ.external_problem_id and integ.sync_status not in ("unlinked",):
        raise SyncError(f"Already linked to Polygon problem {integ.external_problem_id}", "duplicate")
    if integ.sync_status in ("creating", "create_unknown"):
        raise SyncError("A previous creation attempt has an unknown outcome; reconcile it first", "ambiguous")
    existing = [p for p in (client.call("problems.list", {"name": name}) or [])
                if p.get("name") == name and not p.get("deleted")]
    if existing:
        raise SyncError(f"A Polygon problem named '{name}' already exists (id {existing[0].get('id')}); "
                        f"link it instead of creating a duplicate", "duplicate")
    integ.pending_create = {"name": name, "requested_at": _now().isoformat()}
    integ.sync_status = "creating"
    db.commit()
    try:
        created = client.call("problem.create", {"name": name}, write=True)
    except PolygonError as e:
        if e.kind == "ambiguous":
            return reconcile_create(db, problem, client)
        integ.pending_create, integ.sync_status = None, "unlinked"
        db.commit()
        raise
    if not isinstance(created, dict) or "id" not in created:
        integ.sync_status = "create_unknown"
        db.commit()
        raise SyncError("Polygon did not return the created problem; use 'reconcile creation'", "ambiguous")
    _link(db, integ, created, "created")
    return integ


def reconcile_create(db: Session, problem: Problem, client: PolygonClient) -> ProblemIntegration:
    integ = get_integration(db, problem)
    if not integ or not integ.pending_create:
        raise SyncError("No pending creation to reconcile")
    name = integ.pending_create["name"]
    found = [p for p in (client.call("problems.list", {"name": name}) or [])
             if p.get("name") == name and not p.get("deleted")]
    if len(found) == 1:
        _link(db, integ, found[0], "created")
        return integ
    integ.sync_status = "create_unknown" if not found else "create_unknown"
    db.commit()
    if not found:
        integ.pending_create, integ.sync_status = None, "unlinked"
        db.commit()
        raise SyncError(f"No Polygon problem named '{name}' exists; the creation did not happen. You may retry.",
                        "not_found")
    raise SyncError(f"{len(found)} problems named '{name}' found; link the right one manually", "ambiguous")


def link_problem(db: Session, problem: Problem, client: PolygonClient, polygon_id: str,
                 confirm_name: str) -> ProblemIntegration:
    remote = fetch_remote_problem(client, polygon_id)
    if remote.get("deleted"):
        raise SyncError("That Polygon problem is deleted")
    if remote.get("name") != confirm_name:
        raise SyncError(f"Confirmation name does not match the remote problem name ('{remote.get('name')}')")
    other = (db.query(ProblemIntegration).filter(ProblemIntegration.platform_name == "polygon",
                                                 ProblemIntegration.external_problem_id == str(polygon_id),
                                                 ProblemIntegration.problem_id != problem.id).first())
    if other:
        raise SyncError("That Polygon problem is already linked to another local problem", "duplicate")
    integ = get_integration(db, problem, create=True)
    if integ.external_problem_id and integ.external_problem_id != str(polygon_id) and integ.sync_status != "unlinked":
        raise SyncError(f"Already linked to Polygon problem {integ.external_problem_id}; unlink first", "duplicate")
    _link(db, integ, remote, "linked")
    return integ


def _link(db, integ, remote: dict, mode: str) -> None:
    if str(integ.external_problem_id or "") != str(remote["id"]):
        db.query(PolygonItemState).filter_by(integration_id=integ.id).delete()
    integ.external_problem_id = str(remote["id"])
    integ.link_mode, integ.pending_create, integ.sync_status = mode, None, "linked"
    _apply_remote_problem(integ, remote)
    db.commit()


def unlink(db: Session, integ: ProblemIntegration) -> None:
    """Local-only: forget the mapping. Nothing is changed on Polygon."""
    db.query(PolygonItemState).filter_by(integration_id=integ.id).delete()
    integ.external_problem_id = None
    integ.sync_status, integ.link_mode = "unlinked", None
    for f in ("remote_name", "remote_owner", "access_type", "remote_revision", "working_copy_revision",
              "remote_modified", "pending_create", "last_commit", "last_build"):
        setattr(integ, f, None)
    db.commit()


# ── remote snapshot ───────────────────────────────────────────────────────────
class Remote:
    def __init__(self, client: PolygonClient, pid: str, items: List[LocalItem]):
        self.c, self.pid = client, pid
        types = {i.type for i in items}
        self.problem = fetch_remote_problem(client, pid)
        self.info = self._r("problem.info") if "info" in types else None
        files = self._r("problem.files") if types & {"file", "assign"} else {}
        self.source_files = {f["name"]: f for f in (files or {}).get("sourceFiles", [])}
        self.solutions = {s["name"]: s for s in (self._r("problem.solutions") or [])} if "solution" in types else {}
        self.validator = self._r("problem.validator") if "assign" in types else None
        self.checker = self._r("problem.checker") if "assign" in types else None
        self.statements = (self._r("problem.statements") or {}) if types & {"statement", "tutorial"} else {}
        ts = get_settings().POLYGON_TESTSET
        self.tests = {int(t["index"]): t for t in (self._r("problem.tests", {"testset": ts}) or [])} \
            if "test" in types else {}

    def _r(self, method, params=None):
        return self.c.call(method, {"problemId": self.pid, **(params or {})})

    def view(self, item: LocalItem) -> Optional[str]:
        method = "problem.viewSolution" if item.type == "solution" else "problem.viewFile"
        params = {"name": item.remote_name} if item.type == "solution" else {"type": "source", "name": item.remote_name}
        raw = self._r(method, params)
        return raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else None


def _test_input(t: dict) -> Optional[str]:
    if t.get("inputBase64"):
        try:
            return base64.b64decode(t["inputBase64"]).decode("utf-8", "replace")
        except (ValueError, TypeError):
            return None
    return t.get("input")


def _meta(entry: Optional[dict]) -> Optional[dict]:
    if not entry:
        return None
    return {k: entry.get(k) for k in ("modificationTimeSeconds", "length", "tag", "sourceType") if k in entry}


# ── planning ──────────────────────────────────────────────────────────────────
def plan(db: Session, problem: Problem, integ: Optional[ProblemIntegration], scope: dict,
         client: Optional[PolygonClient]) -> dict:
    return plan_full(db, problem, integ, scope, client)[0]


def plan_full(db: Session, problem: Problem, integ: Optional[ProblemIntegration], scope: dict,
              client: Optional[PolygonClient]):
    items = build_local_items(db, problem, scope)
    states = {s.item_key: s for s in db.query(PolygonItemState).filter_by(integration_id=integ.id).all()} \
        if integ and integ.id else {}
    overwrite = set(scope.get("overwrite_remote") or [])
    warnings: List[str] = []
    remote = None
    if client is not None:
        require_linked(integ)
        remote = Remote(client, integ.external_problem_id, items)
        p = remote.problem
        _apply_remote_problem(integ, p)
        if p.get("accessType") == "READ":
            warnings.append("Your access to this Polygon problem is READ only; uploads and commits will fail.")
        if p.get("workingCopyRevision") is not None and p.get("revision") is not None \
                and p["workingCopyRevision"] < p["revision"]:
            warnings.append(f"Your working copy (revision {p['workingCopyRevision']}) is older than the latest "
                            f"revision {p['revision']}. Update the working copy explicitly before syncing.")
        if p.get("modified"):
            warnings.append("The Polygon working copy already has uncommitted changes (possibly made in the web UI). "
                            "They are kept and will be included in your next commit.")

    rows = []
    used_indices = set(remote.tests) if remote else set()
    for it in items:
        st = states.get(it.key)
        row = {**it.public(), "state": _state_label(st, it), "action": None, "reason": None}
        if it.blocked:
            row["action"], row["reason"] = "blocked", it.blocked
        elif remote is None:
            row["action"] = "unchanged" if row["state"] == "uploaded" else "upload"
            row["reason"] = "Local preview only — remote state not checked (run a dry run)"
        else:
            row["action"], row["reason"], extra = _decide(it, st, remote, overwrite, used_indices)
            row.update(extra)
        rows.append(row)

    blocked_keys = {r["key"] for r in rows if r["action"] in ("blocked", "conflict")}
    for r in rows:   # dependency blocking (e.g. setChecker needs checker file)
        dep = [d for d in r["depends_on"] if d in blocked_keys]
        if dep and r["action"] in ACTIONABLE:
            r["action"], r["reason"] = "blocked", f"Depends on {', '.join(dep)}"
    rows.sort(key=lambda r: (ORDER.get(r["type"], 9), r.get("remote_index") or 0))
    if remote is not None and any(w.startswith("Your working copy") or "READ only" in w for w in warnings):
        for r in rows:
            if r["action"] in ACTIONABLE:
                r["action"], r["reason"] = "blocked", "Working copy outdated or insufficient access"
    fp = hashlib.sha256(json.dumps([(r["key"], r["action"], r["local_hash"], r.get("remote_index"))
                                    for r in rows], sort_keys=True).encode()).hexdigest()
    remote_only = []
    if remote is not None:
        mapped = {r.get("remote_index") for r in rows if r["type"] == "test"}
        remote_only = sorted(i for i in remote.tests if i not in mapped)
    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
    return ({"items": rows, "warnings": warnings, "fingerprint": fp, "counts": counts,
            "remote_checked": remote is not None,
            "remote_problem": remote.problem if remote else None,
            "remote_only_tests": remote_only,
            "not_supported": ["Test scripts (problem.saveScript): tests are uploaded as explicit manual tests",
                              "Statement resources (images): no local resource artifacts exist",
                              "Test groups/points: local tests have no groups",
                              "Expected answers are computed by Polygon from the main (MA) solution"]},
            {it.key: it for it in items}, remote)


def _state_label(st: Optional[PolygonItemState], it: LocalItem) -> str:
    if st is None:
        return "not_uploaded"
    if st.status == "uploaded":
        return "uploaded" if st.local_hash == it.local_hash else "changed_locally"
    return st.status  # failed | unknown | pending


def _decide(it: LocalItem, st, remote: Remote, overwrite: set, used: set) -> Tuple[str, str, dict]:
    if it.type == "info":
        cur = remote.info or {}
        changes = {k: v for k, v in it.payload.items() if cur.get(k) != v}
        it.payload = changes
        return ("update", f"Changes: {changes}", {"changes": changes}) if changes else ("unchanged", "Matches remote", {})
    if it.type in ("statement", "tutorial"):
        lang = it.payload["lang"]
        cur = remote.statements.get(lang)
        fields = {k: v for k, v in it.payload.items() if k != "lang"}
        if cur is None:
            if it.type == "statement":
                it.payload["encoding"] = "UTF-8"
            return "create", f"No {lang} statement on Polygon", {"changes": sorted(fields)}
        changed = sorted(k for k, v in fields.items() if norm(cur.get(k)) != norm(v))
        it.payload = {"lang": lang, **{k: fields[k] for k in changed}}
        return ("update", f"Fields changed: {', '.join(changed)}", {"changes": changed}) if changed \
            else ("unchanged", "Matches remote", {})
    if it.type == "assign":
        role = next(iter(it.payload))
        cur = remote.validator if role == "validator" else remote.checker
        return ("unchanged", f"Remote {role} is {cur}", {}) if cur == it.payload[role] \
            else ("update", f"Remote {role}: {cur or '(none)'} → {it.payload[role]}", {})
    if it.type in ("file", "solution"):
        entry = (remote.solutions if it.type == "solution" else remote.source_files).get(it.remote_name)
        if entry is None:
            note = " (it was uploaded before but no longer exists remotely)" if st and st.status == "uploaded" else ""
            it.payload["checkExisting"] = True
            return "create", f"Not on Polygon{note}", {}
        it.payload["checkExisting"] = False
        ours = st is not None and st.status == "uploaded" and st.remote_meta == _meta(entry)
        if ours and st.local_hash == it.local_hash:
            return "unchanged", "Up to date", {}
        if ours:
            if st.local_version and it.local_version and it.local_version < st.local_version:
                return "conflict", (f"Local version v{it.local_version} is older than uploaded v{st.local_version}; "
                                    f"refusing to overwrite with an older version"), {}
            return "update", "Changed locally since last upload (remote untouched)", {}
        content = remote.view(it)
        if content is not None and norm(content) == norm(it.payload["file"]):
            return "unchanged", "Remote file already has identical content", {"adopt_meta": _meta(entry)}
        if it.key in overwrite:
            return "update", "Remote file differs — overwrite explicitly approved", {}
        return "conflict", ("Remote file exists with different content that PolyPilot did not upload "
                            "(or it was modified on Polygon). Approve overwrite explicitly to replace it."), {}
    if it.type == "test":
        local = norm(it.payload["testInput"])
        if st and st.status == "uploaded" and st.remote_index in remote.tests:
            rin = _test_input(remote.tests[st.remote_index])
            if rin is not None and norm(rin) == local:
                it.remote_index = st.remote_index
                return "unchanged", f"Remote test #{st.remote_index} matches", {"remote_index": st.remote_index}
            if rin is not None and sha(norm(rin)) == (st.remote_meta or {}).get("input_sha"):
                it.remote_index = st.remote_index
                it.payload.update(testIndex=st.remote_index, checkExisting=False)
                return "update", f"Update remote test #{st.remote_index} (local input changed)", {"remote_index": st.remote_index}
        for idx, t in remote.tests.items():   # duplicate detection
            rin = _test_input(t)
            if rin is not None and norm(rin) == local:
                it.remote_index = idx
                return "unchanged", f"Identical input already present as remote test #{idx}", \
                    {"remote_index": idx, "adopt_index": idx}
        idx = max(used, default=0) + 1
        used.add(idx)
        it.remote_index = idx
        it.payload.update(testIndex=idx, checkExisting=True)
        return "create", f"Add as test #{idx}", {"remote_index": idx}
    return "blocked", f"Unsupported item type {it.type}", {}


# ── execution ─────────────────────────────────────────────────────────────────
WRITE_METHOD = {"info": "problem.updateInfo", "statement": "problem.saveStatement", "tutorial": "problem.saveStatement",
                "file": "problem.saveFile", "solution": "problem.saveSolution", "test": "problem.saveTest"}


def _assign_method(it: LocalItem) -> str:
    return "problem.setValidator" if "validator" in it.payload else "problem.setChecker"


def _upsert_state(db, integ, it: LocalItem, status: str, error: Optional[str] = None, meta: Optional[dict] = None):
    st = db.query(PolygonItemState).filter_by(integration_id=integ.id, item_key=it.key).first()
    if st is None:
        st = PolygonItemState(problem_id=integ.problem_id, integration_id=integ.id, item_key=it.key, item_type=it.type)
        db.add(st)
    st.local_ref, st.local_version, st.remote_name = it.local_ref, it.local_version, it.remote_name
    st.remote_index = it.remote_index
    st.status, st.error = status, error
    if status == "uploaded":
        st.local_hash, st.uploaded_at = it.local_hash, _now()
    if meta is not None:
        st.remote_meta = meta
    db.commit()


def _verify(remote_items: Remote, it: LocalItem) -> Tuple[Optional[bool], Optional[dict]]:
    """Read back one item. Returns (matches, remote_meta) — None if it cannot be determined."""
    c, pid = remote_items.c, remote_items.pid
    if it.type == "info":
        info = c.call("problem.info", {"problemId": pid}) or {}
        return all(info.get(k) == v for k, v in it.payload.items()), None
    if it.type in ("statement", "tutorial"):
        cur = (c.call("problem.statements", {"problemId": pid}) or {}).get(it.payload["lang"])
        if cur is None:
            return False, None
        return all(norm(cur.get(k)) == norm(v) for k, v in it.payload.items() if k not in ("lang", "encoding")), None
    if it.type == "assign":
        role = next(iter(it.payload))
        return c.call(f"problem.{role}", {"problemId": pid}) == it.payload[role], None
    if it.type in ("file", "solution"):
        content = remote_items.view(it)
        if content is None:
            return None, None
        listing = (c.call("problem.solutions", {"problemId": pid}) or []) if it.type == "solution" else \
            ((c.call("problem.files", {"problemId": pid}) or {}).get("sourceFiles") or [])
        entry = next((e for e in listing if e.get("name") == it.remote_name), None)
        return norm(content) == norm(it.payload["file"]), _meta(entry)
    if it.type == "test":
        # problem.tests (not problem.testInput): observed live, testInput fails with HTTP 400 until the
        # problem has a main solution, while problem.tests returns manual test inputs.
        tests = c.call("problem.tests", {"problemId": pid, "testset": it.payload["testset"]}) or []
        t = next((x for x in tests if int(x.get("index", -1)) == int(it.remote_index or -1)), None)
        text = _test_input(t) if t else None
        if t is None:
            return False, None
        return (None, None) if text is None else (norm(text) == norm(it.payload["testInput"]), {"input_sha": sha(norm(text))})
    return None, None


def execute(db: Session, run: PolygonSyncRun, problem: Problem, integ: ProblemIntegration,
            client: PolygonClient) -> PolygonSyncRun:
    """Re-plan against fresh remote state; abort if it differs from the approved dry run."""
    run.status, run.started_at = "running", _now()
    integ.sync_status = "syncing"
    db.commit()
    results: List[dict] = []
    try:
        fresh, by_key, remote = plan_full(db, problem, integ, run.scope or {}, client)
        approved = (run.plan or {}).get("fingerprint")
        if approved != fresh["fingerprint"]:
            raise SyncError("Local or remote state changed since the dry run was reviewed. Run a new dry run.", "stale_plan")
        failed_keys = set()
        for row in fresh["items"]:
            it = by_key[row["key"]]
            if row["action"] == "unchanged" and (row.get("adopt_meta") is not None or row.get("adopt_index")):
                _upsert_state(db, integ, it, "uploaded", meta=row.get("adopt_meta") or
                              ({"input_sha": it.local_hash} if it.type == "test" else None))
                results.append({"key": it.key, "outcome": "adopted", "detail": row["reason"]})
                continue
            if row["action"] not in ACTIONABLE:
                continue
            if any(d in failed_keys for d in it.depends_on):
                results.append({"key": it.key, "outcome": "skipped", "detail": "dependency failed"})
                continue
            outcome = _write(db, client, integ, remote, it)
            results.append(outcome)
            if outcome["outcome"] not in ("uploaded",):
                failed_keys.add(it.key)
            if outcome.get("kind") == "rate_limited":
                results.append({"key": "*", "outcome": "stopped", "detail": "Rate limited — resume later"})
                break
            run.result = {"operations": results}
            db.commit()
        ok = [r for r in results if r["outcome"] in ("uploaded", "adopted")]
        bad = [r for r in results if r["outcome"] not in ("uploaded", "adopted")]
        run.status = "completed" if not bad else ("partial" if ok else "failed")
        run.summary = f"{len(ok)} items confirmed on Polygon, {len(bad)} failed/unknown/skipped. Not committed."
        refresh(db, integ, client)
        integ.sync_status = "synced" if not bad else "partial"
        integ.last_synced_at = _now()
    except (PolygonError, SyncError) as e:
        run.status = "failed" if not results else "partial"
        run.summary = f"{getattr(e, 'kind', 'error')}: {e.message}"
        integ.sync_status = "partial" if results else "linked"
    run.result = {**(run.result or {}), "operations": results}
    run.completed_at = _now()
    db.commit()
    return run


def _write(db, client, integ, remote: Remote, it: LocalItem) -> dict:
    method = _assign_method(it) if it.type == "assign" else WRITE_METHOD[it.type]
    params = {"problemId": integ.external_problem_id, **it.payload}
    _upsert_state(db, integ, it, "pending")
    try:
        client.call(method, params, write=True)
    except PolygonError as e:
        if e.kind != "ambiguous":
            _upsert_state(db, integ, it, "failed", f"{e.kind}: {e.message}")
            return {"key": it.key, "outcome": "failed", "kind": e.kind, "detail": e.message}
        # Ambiguous: reconcile through read methods before deciding anything.
        try:
            matches, meta = _verify(remote, it)
        except PolygonError as e2:
            matches, meta = None, None
            logger.warning("reconcile read failed: %s", e2.message)
        if matches:
            _upsert_state(db, integ, it, "uploaded", meta=meta)
            return {"key": it.key, "outcome": "uploaded", "detail": "Outcome was ambiguous; read-back confirms it applied"}
        status = "failed" if matches is False else "unknown"
        _upsert_state(db, integ, it, status, f"ambiguous write; read-back: {'not applied' if matches is False else 'unknown'}")
        return {"key": it.key, "outcome": status, "kind": "ambiguous", "detail": e.message}
    try:
        matches, meta = _verify(remote, it)
    except PolygonError as e:
        _upsert_state(db, integ, it, "unknown", f"write OK but read-back failed: {e.message}")
        return {"key": it.key, "outcome": "unknown", "kind": e.kind, "detail": "Polygon accepted the write; read-back failed"}
    if matches is False:
        _upsert_state(db, integ, it, "failed", "Polygon returned OK but read-back content differs")
        return {"key": it.key, "outcome": "failed", "detail": "read-back mismatch"}
    _upsert_state(db, integ, it, "uploaded" if matches else "unknown", meta=meta)
    return {"key": it.key, "outcome": "uploaded" if matches else "unknown",
            "detail": f"{method} OK" + (", verified by read-back" if matches else ", read-back inconclusive")}


# ── working copy / commit / build ─────────────────────────────────────────────
def update_working_copy(db, integ, client) -> dict:
    client.call("problem.updateWorkingCopy", {"problemId": integ.external_problem_id}, write=True)
    return refresh(db, integ, client)


def discard_working_copy(db, integ, client) -> dict:
    client.call("problem.discardWorkingCopy", {"problemId": integ.external_problem_id}, write=True)
    db.query(PolygonItemState).filter_by(integration_id=integ.id).update({"status": "unknown",
                                                                           "error": "working copy discarded"})
    db.commit()
    return refresh(db, integ, client)


def commit(db, integ, client, message: str, minor: bool) -> dict:
    before = fetch_remote_problem(client, integ.external_problem_id)
    try:
        res = client.call("problem.commitChanges", {"problemId": integ.external_problem_id,
                                                    "message": message, "minorChanges": minor}, write=True)
        outcome = {"confirmed": True, "committed": bool((res or {}).get("committed")),
                   "conflictOccurred": bool((res or {}).get("conflictOccurred")), "message": (res or {}).get("message")}
    except PolygonError as e:
        if e.kind != "ambiguous":
            raise
        after = fetch_remote_problem(client, integ.external_problem_id)
        applied = (after.get("revision") or 0) > (before.get("revision") or 0)
        outcome = {"confirmed": applied, "committed": applied, "conflictOccurred": None,
                   "message": "Outcome was ambiguous; revision increased" if applied else
                   "Outcome ambiguous; revision did not change — commit status unknown"}
    after = refresh(db, integ, client)
    outcome.update(revision_before=before.get("revision"), revision_after=after.get("revision"),
                   commit_message=message, at=_now().isoformat())
    integ.last_commit = outcome
    db.commit()
    return outcome


def build_preflight(db, problem, integ, client) -> dict:
    p = refresh(db, integ, client)
    cautions = client.call("problem.cautions", {"problemId": integ.external_problem_id}) or {}
    readiness = cautions.get("packageReadinessIssues") or []
    hard = [c for k in ("common", "statement", "structure", "issues") for c in (cautions.get(k) or [])
            if c.get("severity") == "HARD"]
    phase4 = {}
    for t in ("validator", "reference", "differential"):
        r = (db.query(VerificationRun).filter_by(problem_id=problem.id, test_type=t)
             .order_by(VerificationRun.created_at.desc()).first())
        phase4[t] = r.status if r else "not_run"
    states = db.query(PolygonItemState).filter_by(integration_id=integ.id).all()
    problems = [f"Polygon readiness: {i.get('message') or i.get('type')}" for i in readiness]
    problems += [f"Hard caution: {c.get('message') or c.get('type')}" for c in hard]
    problems += [f"Phase 4 {t} is {s}" for t, s in phase4.items() if s != "passed"]
    if p.get("modified"):
        problems.append("The working copy has uncommitted changes; packages are built from committed revisions")
    bad = [s.item_key for s in states if s.status in ("failed", "unknown", "pending")]
    if bad:
        problems.append(f"{len(bad)} items have failed/unknown sync status")
    return {"remote_problem": p, "readiness_issues": readiness, "hard_cautions": hard, "phase4": phase4,
            "items_not_confirmed": bad, "issues": problems, "ready": not problems}


def build(db, integ, client, full: bool, verify: bool) -> dict:
    requested = int(time.time() + PolygonClient._clock_offset)
    try:
        client.call("problem.buildPackage", {"problemId": integ.external_problem_id, "full": full, "verify": verify},
                    write=True)
        request_status = "submitted"
        err = None
    except PolygonError as e:
        if e.kind != "ambiguous":
            integ.last_build = {"request_status": "failed", "error": e.message, "requested_at": requested,
                                "full": full, "verify": verify}
            db.commit()
            raise
        request_status, err = "unknown", e.message
    integ.last_build = {"request_status": request_status, "requested_at": requested, "full": full,
                        "verify": verify, "error": err, "state": "submitted" if request_status == "submitted" else "unknown"}
    db.commit()
    return build_status(db, integ, client)


BUILD_STATE = {"PENDING": "submitted", "RUNNING": "building", "READY": "built", "FAILED": "failed"}


def build_status(db, integ, client) -> dict:
    packages = client.call("problem.packages", {"problemId": integ.external_problem_id}) or []
    lb = dict(integ.last_build or {})
    out = {"packages": packages, "last_build": lb, "state": "not_started"}
    if lb:
        since = int(lb.get("requested_at") or 0) - 120
        recent = sorted([p for p in packages if int(p.get("creationTimeSeconds") or 0) >= since],
                        key=lambda p: p.get("creationTimeSeconds") or 0, reverse=True)
        if recent:
            pk = recent[0]
            lb.update(state=BUILD_STATE.get(pk.get("state"), "unknown"), package_id=pk.get("id"),
                      package_revision=pk.get("revision"), package_comment=pk.get("comment"),
                      package_type=pk.get("type"), checked_at=_now().isoformat())
        elif lb.get("request_status") == "submitted":
            lb["state"] = "submitted"
        else:
            lb["state"] = "unknown"
        integ.last_build = lb
        db.commit()
        out["last_build"], out["state"] = lb, lb["state"]
    return out
