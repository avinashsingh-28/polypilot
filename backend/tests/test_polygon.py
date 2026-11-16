"""Phase 5 Polygon integration tests — all against an in-memory fake (no real Polygon calls)."""
import hashlib
import json
import time
import uuid

import pytest
from cryptography.fernet import Fernet

from app.api.routes import polygon as routes
from app.core.config import get_settings
from app.main import app
from app.models.artifact import ProblemArtifact
from app.models.polygon import PolygonAccount, PolygonItemState, PolygonOperation, PolygonSyncRun
from app.models.problem import Problem
from app.models.test_case import TestCase
from app.models.verification import VerificationRun
from app.services.polygon import credentials as cred
from app.services.polygon import sync as S
from app.services.polygon.client import (Credentials, PolygonClient, PolygonError, compute_api_sig,
                                         normalize_params, signature_base, validate_base_url)
from app.services.polygon.mapping import build_local_items, md_to_polygon, parse_statement, sha
from tests.fake_polygon import KEY, SECRET, FakePolygon
from tests.sandbox_fixtures import BRUTE, CHECKER, GENERATOR, REFERENCE, VALIDATOR

API = "/api/v1"


# ── fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture
def fake():
    return FakePolygon()


@pytest.fixture
def env_creds(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "POLYGON_API_KEY", KEY)
    monkeypatch.setattr(s, "POLYGON_API_SECRET", SECRET)
    monkeypatch.setattr(s, "POLYGON_MIN_INTERVAL_SEC", 0.0)
    monkeypatch.setattr("app.services.polygon.client.time.sleep", lambda s: None)
    return s


@pytest.fixture
def api(client, db_session, fake, env_creds):
    def inline(run_id, transport):
        run = db_session.get(PolygonSyncRun, run_id)
        problem = db_session.get(Problem, run.problem_id)
        from app.models.user import User
        owner = db_session.get(User, problem.owner_id)
        with cred.make_client(db_session, owner, problem.id, run.id, transport) as c:
            S.execute(db_session, run, problem, S.get_integration(db_session, problem), c)
    app.dependency_overrides[routes.get_polygon_transport] = lambda: fake.transport()
    app.dependency_overrides[routes.get_sync_executor] = lambda: inline
    yield client
    app.dependency_overrides.pop(routes.get_polygon_transport, None)
    app.dependency_overrides.pop(routes.get_sync_executor, None)


def _verified(db, pid, test_type, role, src, status="passed"):
    db.add(VerificationRun(problem_id=pid, test_type=test_type, status=status, summary=f"{test_type} {status}",
                           report={"compilations": {role: {"source_sha256": sha(src)}}}))


@pytest.fixture
def local_problem(db_session, auth_user):
    p = Problem(owner_id=auth_user.id, title="Sum Array", slug=f"sum-{uuid.uuid4().hex[:6]}", time_limit_seconds=1, memory_limit_mb=256,
                idea="sum", difficulty="Div. 2 A")
    db_session.add(p)
    db_session.flush()
    spec = {"problem_name": "Sum Array", "legend": "Add numbers.", "formal_statement": "Given $n$ integers.",
            "input_format": "First line $n$.", "output_format": "The sum.", "samples": []}
    statement = ("# Sum Array\n\nYou are given $n$ integers $a_1, \\ldots, a_n$. Find **their sum**.\n\n"
                 "## Input\nThe first line contains $n$ ($1 \\le n \\le 10$).\n\n## Output\nPrint $\\sum a_i$.\n\n"
                 "## Examples\n```\n3\n1 2 3\n```\n\n## Note\nÜnïcödé & <ok> 100%")
    for t, c in (("specification", json.dumps(spec)), ("statement", statement), ("validator", VALIDATOR),
                 ("generator", GENERATOR), ("reference_solution", REFERENCE), ("brute_force", BRUTE),
                 ("editorial", "Just **add** them: $O(n)$.")):
        db_session.add(ProblemArtifact(problem_id=p.id, artifact_type=t, content=c, language="cpp"))
    _verified(db_session, p.id, "validator", "validator", VALIDATOR)
    _verified(db_session, p.id, "generate", "gen", GENERATOR)
    _verified(db_session, p.id, "reference", "reference", REFERENCE)
    _verified(db_session, p.id, "differential", "candidate", BRUTE)
    for i, (typ, inp, st) in enumerate((("sample", "3\n1 2 3\n", "valid"), ("generated", "2\n5 -1\n", "valid"),
                                        ("generated", "1\n7\n", "invalid"), ("manual", "4\n1 1 1 1\n", "unchecked"))):
        db_session.add(TestCase(problem_id=p.id, test_type=typ, input_data=inp, validation_status=st,
                                is_valid=st == "valid"))
        db_session.flush()
    db_session.commit()
    return p


def _link(api, fake, pid, name="sum-array"):
    rp = fake.add_problem(name)
    r = api.post(f"{API}/problems/{pid}/polygon/link", json={"polygon_problem_id": str(rp["id"]), "confirm_name": name})
    assert r.status_code == 200, r.text
    return rp


# ── signing ───────────────────────────────────────────────────────────────────
def test_signature_known_vector():
    pairs = [("problemId", "5"), ("apiKey", "xxx"), ("time", "1")]
    base = signature_base("abcdef", "problem.info", pairs)
    assert base == "abcdef/problem.info?apiKey=xxx&problemId=5&time=1"
    want = "abcdef" + hashlib.sha512(b"abcdef/problem.info?apiKey=xxx&problemId=5&time=1#secret").hexdigest()
    assert compute_api_sig("abcdef", "problem.info", pairs, "secret") == want
    assert len(want) == 6 + 128


def test_sorting_by_name_then_value_and_raw_values():
    pairs = normalize_params({"testIndex": ["2", "10"], "a": "x y&z=ü", "flag": True, "skip": None})
    assert ("skip", "None") not in pairs and ("flag", "true") in pairs
    assert signature_base("rrrrrr", "m", pairs) == "rrrrrr/m?a=x y&z=ü&flag=true&testIndex=10&testIndex=2"
    with pytest.raises(ValueError):
        compute_api_sig("abc", "m", pairs, "s")


def test_request_construction_and_url_encoding(fake, env_creds):
    c = PolygonClient(Credentials(KEY, SECRET, "env"), transport=fake.transport(), min_interval=0)
    p = fake.add_problem("enc")
    c.call("problem.saveStatement", {"problemId": p["id"], "lang": "english", "legend": "a & b = $x^2$ 100% ü\nline2"},
           write=True)
    assert fake.problems[p["id"]]["statements"]["english"]["legend"] == "a & b = $x^2$ 100% ü\nline2"
    method, params = fake.calls[-1]
    assert params["apiKey"] == KEY and len(params["apiSig"]) == 134 and abs(int(params["time"]) - time.time()) < 5


def test_only_official_host_allowed():
    for bad in ("http://polygon.codeforces.com/api", "https://evil.example/api", "https://polygon.codeforces.com.evil.io/api",
                "https://user:pw@polygon.codeforces.com/api"):
        with pytest.raises(PolygonError):
            validate_base_url(bad)
    assert validate_base_url("https://polygon.codeforces.com/api/") == "https://polygon.codeforces.com/api"


# ── response parsing / errors / retries ──────────────────────────────────────
def _client(fake, secret=SECRET, key=KEY):
    return PolygonClient(Credentials(key, secret, "env"), transport=fake.transport(), min_interval=0, sleep=lambda s: None)


def test_error_classification(fake):
    with pytest.raises(PolygonError) as e:
        _client(fake, secret="wrong").call("problems.list")
    assert e.value.kind == "invalid_credentials"
    with pytest.raises(PolygonError) as e:
        _client(fake, key="nokey123").call("problems.list")
    assert e.value.kind == "invalid_credentials"
    with pytest.raises(PolygonError) as e:
        _client(fake).call("problem.info", {"problemId": 999})
    assert e.value.kind == "not_found"
    fake.add_problem("x", access="NONE")
    with pytest.raises(PolygonError) as e:
        _client(fake).call("problem.info", {"problemId": 1000})
    assert e.value.kind == "permission_denied"
    with pytest.raises(PolygonError):
        PolygonClient(None)


def test_reads_retry_but_writes_never_retry(fake):
    p = fake.add_problem("r")
    fake.fail["problem.info"] = "500"
    assert _client(fake).call("problem.info", {"problemId": p["id"]})["timeLimit"] == 2000
    assert [m for m, _ in fake.calls].count("problem.info") == 2
    fake.fail["problems.list"] = "429"
    assert _client(fake).call("problems.list") is not None          # rate limit retried for reads
    fake.fail["problem.updateInfo"] = "500"
    with pytest.raises(PolygonError) as e:
        _client(fake).call("problem.updateInfo", {"problemId": p["id"], "timeLimit": 2000}, write=True)
    assert e.value.kind == "ambiguous"
    assert [m for m, _ in fake.calls].count("problem.updateInfo") == 1
    fake.fail["problem.updateInfo"] = "429"
    with pytest.raises(PolygonError) as e:
        _client(fake).call("problem.updateInfo", {"problemId": p["id"], "timeLimit": 2000}, write=True)
    assert e.value.kind == "rate_limited"


def test_clock_skew_is_learned_from_date_header(fake):
    fake.skew = 1000   # server clock 1000s ahead → first request rejected, retried with learned offset
    PolygonClient._clock_offset = 0.0
    try:
        assert _client(fake).call("problems.list") == []
        assert abs(PolygonClient._clock_offset - 1000) < 5
    finally:
        PolygonClient._clock_offset = 0.0


# ── credentials ──────────────────────────────────────────────────────────────
def test_missing_credentials_status(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "POLYGON_API_KEY", "")
    monkeypatch.setattr(s, "POLYGON_API_SECRET", "")
    st = client.get(f"{API}/polygon/status").json()
    assert st["configured"] is False
    r = client.post(f"{API}/polygon/test").json()
    assert r["ok"] is False and r["kind"] == "missing_credentials"


def test_store_credentials_encrypted_and_never_returned(client, db_session, monkeypatch, fake, auth_user):
    s = get_settings()
    monkeypatch.setattr(s, "POLYGON_API_KEY", "")
    monkeypatch.setattr(s, "POLYGON_API_SECRET", "")
    monkeypatch.setattr(s, "POLYGON_CREDENTIALS_KEY", "")
    body = {"api_key": KEY, "api_secret": SECRET}
    assert client.put(f"{API}/polygon/credentials", json=body).status_code == 400   # no encryption key → refused
    monkeypatch.setattr(s, "POLYGON_CREDENTIALS_KEY", Fernet.generate_key().decode())
    r = client.put(f"{API}/polygon/credentials", json=body)
    assert r.status_code == 200 and SECRET not in r.text and KEY not in r.text
    row = db_session.query(PolygonAccount).filter_by(source="stored", user_id=auth_user.id).one()
    assert SECRET not in row.api_secret_encrypted and KEY not in row.api_key_encrypted
    assert cred.load_credentials(db_session, auth_user).api_secret == SECRET
    app.dependency_overrides[routes.get_polygon_transport] = lambda: fake.transport()
    try:
        t = client.post(f"{API}/polygon/test").json()
    finally:
        app.dependency_overrides.pop(routes.get_polygon_transport, None)
    assert t["ok"] is True and t["status"]["last_success_at"]
    assert SECRET not in json.dumps(t)
    assert client.delete(f"{API}/polygon/credentials").json()["configured"] is False


# ── mapping ──────────────────────────────────────────────────────────────────
def test_statement_parsing_and_latex_preservation():
    md = "# Title\nLegend **bold** and $a*b*c$ with `code`.\n## Input\nIn $$\\sum_{i}^{n} x_i$$\n## Output\nOut\n## Examples\nX\n## Note\nN"
    s = parse_statement(md)
    assert s["legend"].startswith("Legend") and s["input"].startswith("In") and "X" not in s["notes"]
    out = md_to_polygon(s["legend"])
    assert "\\textbf{bold}" in out and "$a*b*c$" in out and "\\texttt{code}" in out
    assert md_to_polygon("$$\\sum_{i}^{n} x_i$$") == "$$\\sum_{i}^{n} x_i$$"


def test_local_items_gating(db_session, local_problem):
    items = {i.key: i for i in build_local_items(db_session, local_problem, {})}
    assert items["info"].payload["timeLimit"] == 1000 and items["info"].blocked is None
    assert items["validator"].blocked is None and items["assign:validator"].payload == {"validator": "validator.cpp"}
    # no custom checker artifact → PolyPilot's built-in token checker is uploaded and set (Polygon requires one)
    assert items["checker"].remote_name == "checker.cpp" and "registerTestlibCmd" in items["checker"].payload["file"]
    assert items["assign:checker"].payload == {"checker": "checker.cpp"} and items["checker"].blocked is None
    tests = [i for i in items.values() if i.type == "test"]
    assert len(tests) == 2                             # only validator-accepted tests
    assert tests[0].payload["testUseInStatements"] is True     # sample first, used in statement
    sols = {i.remote_name: i for i in items.values() if i.type == "solution"}
    assert sols["main.cpp"].payload["tag"] == "MA" and sols["brute.cpp"].payload["tag"] == "TO"
    st = items["statement:english"]
    assert st.payload["name"] == "Sum Array" and "Ünïcödé & <ok> 100%" in st.payload["notes"]
    assert "tutorial:english" not in items             # editorial only when explicitly selected
    local_problem.time_limit_seconds = 1.03
    blocked = [i for i in build_local_items(db_session, local_problem, {}) if i.key == "info"][0]
    assert "divisible by 50" in blocked.blocked


def test_unverified_or_failed_validator_and_checker_are_blocked(db_session, local_problem):
    art = db_session.query(ProblemArtifact).filter_by(problem_id=local_problem.id, artifact_type="validator").one()
    art.content += "\n// changed"
    db_session.add(ProblemArtifact(problem_id=local_problem.id, artifact_type="checker", content=CHECKER))
    _verified(db_session, local_problem.id, "reference", "checker", CHECKER, status="failed")
    db_session.commit()
    items = {i.key: i for i in build_local_items(db_session, local_problem, {})}
    assert items["validator"].blocked and items["assign:validator"].blocked
    assert "failed" in items["checker"].blocked and items["assign:checker"].blocked


# ── create / link ────────────────────────────────────────────────────────────
def test_create_problem_and_duplicate_protection(api, fake, local_problem, db_session):
    pid = local_problem.id
    assert api.post(f"{API}/problems/{pid}/polygon/create", json={"name": "Bad Name"}).status_code == 422
    assert api.post(f"{API}/problems/{pid}/polygon/create", json={"name": "sum-array"}).status_code == 422  # no confirm
    fake.add_problem("taken")
    r = api.post(f"{API}/problems/{pid}/polygon/create", json={"name": "taken", "confirm": True})
    assert r.status_code == 409 and "already exists" in r.json()["detail"]
    r = api.post(f"{API}/problems/{pid}/polygon/create", json={"name": "sum-array", "confirm": True})
    assert r.status_code == 200, r.text
    integ = r.json()
    assert integ["sync_status"] == "linked" and integ["link_mode"] == "created" and integ["remote_name"] == "sum-array"
    assert api.post(f"{API}/problems/{pid}/polygon/create", json={"name": "other", "confirm": True}).status_code == 409


def test_ambiguous_create_is_reconciled_not_duplicated(api, fake, local_problem):
    fake.fail["problem.create"] = "timeout_after_apply"
    r = api.post(f"{API}/problems/{local_problem.id}/polygon/create", json={"name": "amb-prob", "confirm": True})
    assert r.status_code == 200, r.text
    assert r.json()["external_problem_id"] and sum(p["name"] == "amb-prob" for p in fake.problems.values()) == 1
    assert [m for m, _ in fake.calls].count("problem.create") == 1


def test_ambiguous_create_that_did_not_happen(api, fake, local_problem):
    fake.fail["problem.create"] = "timeout_before_apply"
    r = api.post(f"{API}/problems/{local_problem.id}/polygon/create", json={"name": "lost-prob", "confirm": True})
    assert r.status_code == 404 and "did not happen" in r.json()["detail"]
    assert api.get(f"{API}/problems/{local_problem.id}/polygon").json()["integration"]["sync_status"] == "unlinked"


def test_link_requires_matching_name_and_uniqueness(api, fake, local_problem, db_session):
    rp = fake.add_problem("existing-one")
    r = api.post(f"{API}/problems/{local_problem.id}/polygon/link",
                 json={"polygon_problem_id": str(rp["id"]), "confirm_name": "wrong"})
    assert r.status_code == 422
    assert api.post(f"{API}/problems/{local_problem.id}/polygon/link",
                    json={"polygon_problem_id": "424242", "confirm_name": "x"}).status_code == 404
    assert api.post(f"{API}/problems/{local_problem.id}/polygon/link",
                    json={"polygon_problem_id": str(rp["id"]), "confirm_name": "existing-one"}).status_code == 200
    from tests.conftest import login_client  # noqa: F401
    other = Problem(owner_id=local_problem.owner_id, title="Other", slug="other-x", time_limit_seconds=1, memory_limit_mb=256, idea="i", difficulty="d")
    db_session.add(other)
    db_session.commit()
    r = api.post(f"{API}/problems/{other.id}/polygon/link",
                 json={"polygon_problem_id": str(rp["id"]), "confirm_name": "existing-one"})
    assert r.status_code == 409


# ── preview / dry run / sync ─────────────────────────────────────────────────
def test_preview_makes_no_requests(api, fake, local_problem):
    p = api.post(f"{API}/problems/{local_problem.id}/polygon/preview", json={}).json()
    assert p["remote_checked"] is False and fake.calls == []
    assert {i["action"] for i in p["items"]} <= {"upload", "blocked", "unchanged"}


def test_dry_run_then_sync_then_idempotent(api, fake, local_problem, db_session):
    pid = local_problem.id
    rp = _link(api, fake, pid)
    n_calls = len(fake.calls)
    dr = api.post(f"{API}/problems/{pid}/polygon/dry-run", json={}).json()
    writes = [m for m, _ in fake.calls[n_calls:] if not m.startswith(("problems.list", "problem.info", "problem.files",
                                                                         "problem.solutions", "problem.validator",
                                                                         "problem.checker", "problem.statements",
                                                                         "problem.tests", "problem.view"))]
    assert writes == []                                  # dry run never writes
    acts = {i["key"]: i["action"] for i in dr["plan"]["items"]}
    assert acts["info"] == "update" and acts["validator"] == "create" and acts["assign:validator"] == "update"
    assert sum(1 for k, a in acts.items() if k.startswith("test:") and a == "create") == 2
    assert fake.problems[rp["id"]]["files"] == {}
    # sync requires matching confirmation
    assert api.post(f"{API}/problems/{pid}/polygon/sync", json={"dry_run_id": dr["id"], "confirm_problem_id": "1"}).status_code == 422
    r = api.post(f"{API}/problems/{pid}/polygon/sync", json={"dry_run_id": dr["id"], "confirm_problem_id": str(rp["id"])})
    assert r.status_code == 202, r.text
    run = api.get(f"{API}/problems/{pid}/polygon/runs/{r.json()['id']}").json()
    assert run["status"] == "completed", run["summary"]
    remote = fake.problems[rp["id"]]
    assert remote["validator"] == "validator.cpp" and set(remote["files"]) == {"validator.cpp", "gen.cpp", "checker.cpp"} and remote["checker"] == "checker.cpp"
    assert remote["solutions"]["main.cpp"]["tag"] == "MA" and remote["info"]["timeLimit"] == 1000
    assert remote["tests"][1]["input"] == "3\n1 2 3\n" and remote["tests"][1]["stmt"] is True
    assert "\\textbf{their sum}" in remote["statements"]["english"]["legend"]
    assert "$\\sum a_i$" in remote["statements"]["english"]["output"]
    assert remote["revision"] == 1 and remote["modified"] is True      # NOT committed
    assert all(o["method"] != "problem.commitChanges" for o in run["operations"])
    # secrets never logged
    dump = json.dumps([o.params for o in db_session.query(PolygonOperation).all()])
    assert SECRET not in dump and KEY not in dump and "apiSig" not in dump
    states = {s.item_key: s.status for s in db_session.query(PolygonItemState).all()}
    assert set(states.values()) == {"uploaded"}
    # second dry run: nothing to do
    dr2 = api.post(f"{API}/problems/{pid}/polygon/dry-run", json={}).json()
    assert {i["action"] for i in dr2["plan"]["items"]} <= {"unchanged"}
    assert api.post(f"{API}/problems/{pid}/polygon/sync",
                    json={"dry_run_id": dr2["id"], "confirm_problem_id": str(rp["id"])}).status_code == 422


def test_remote_conflicts_are_not_overwritten(api, fake, local_problem):
    pid = local_problem.id
    rp = _link(api, fake, pid)
    fake.problems[rp["id"]]["files"]["validator.cpp"] = {"content": "// someone else's validator", "mtime": 99}
    fake.problems[rp["id"]]["tests"][1] = {"input": "9\n9 9 9 9 9 9 9 9 9\n", "stmt": False}
    dr = api.post(f"{API}/problems/{pid}/polygon/dry-run", json={}).json()
    acts = {i["key"]: i for i in dr["plan"]["items"]}
    assert acts["validator"]["action"] == "conflict" and acts["assign:validator"]["action"] == "blocked"
    test_idx = sorted(i["remote_index"] for k, i in acts.items() if k.startswith("test:"))
    assert test_idx == [2, 3] and dr["plan"]["remote_only_tests"] == [1]     # remote test #1 untouched
    api.post(f"{API}/problems/{pid}/polygon/sync", json={"dry_run_id": dr["id"], "confirm_problem_id": str(rp["id"])})
    assert fake.problems[rp["id"]]["files"]["validator.cpp"]["content"] == "// someone else's validator"
    assert fake.problems[rp["id"]]["tests"][1]["input"].startswith("9")
    # explicit overwrite approval
    dr = api.post(f"{API}/problems/{pid}/polygon/dry-run", json={"overwrite_remote": ["validator"]}).json()
    assert {i["key"]: i["action"] for i in dr["plan"]["items"]}["validator"] == "update"


def test_stale_dry_run_is_rejected(api, fake, local_problem, db_session):
    pid = local_problem.id
    rp = _link(api, fake, pid)
    dr = api.post(f"{API}/problems/{pid}/polygon/dry-run", json={}).json()
    fake.problems[rp["id"]]["info"]["timeLimit"] = 1000      # remote changed after dry run (info now unchanged)
    r = api.post(f"{API}/problems/{pid}/polygon/sync", json={"dry_run_id": dr["id"], "confirm_problem_id": str(rp["id"])})
    run = api.get(f"{API}/problems/{pid}/polygon/runs/{r.json()['id']}").json()
    assert run["status"] == "failed" and "stale_plan" in run["summary"]
    assert fake.problems[rp["id"]]["files"] == {}


def test_partial_failure_and_resume(api, fake, local_problem, db_session):
    pid = local_problem.id
    rp = _link(api, fake, pid)
    fake.fail["problem.saveSolution"] = "FAILED:Source file is too large"
    dr = api.post(f"{API}/problems/{pid}/polygon/dry-run", json={}).json()
    r = api.post(f"{API}/problems/{pid}/polygon/sync", json={"dry_run_id": dr["id"], "confirm_problem_id": str(rp["id"])})
    run = api.get(f"{API}/problems/{pid}/polygon/runs/{r.json()['id']}").json()
    assert run["status"] == "partial"
    states = {s.item_key: s.status for s in db_session.query(PolygonItemState).all()}
    assert "failed" in states.values() and states["validator"] == "uploaded"
    # resume: only the failed item is re-planned
    dr2 = api.post(f"{API}/problems/{pid}/polygon/dry-run", json={}).json()
    pending = [i["key"] for i in dr2["plan"]["items"] if i["action"] in ("create", "update")]
    assert len(pending) == 1 and pending[0].startswith("solution:")
    api.post(f"{API}/problems/{pid}/polygon/sync", json={"dry_run_id": dr2["id"], "confirm_problem_id": str(rp["id"])})
    assert len(fake.problems[rp["id"]]["solutions"]) == 2


def test_ambiguous_test_upload_is_reconciled(api, fake, local_problem, db_session):
    pid = local_problem.id
    rp = _link(api, fake, pid)
    dr = api.post(f"{API}/problems/{pid}/polygon/dry-run", json={"include": ["tests"]}).json()
    fake.fail["problem.saveTest"] = "timeout_after_apply"
    r = api.post(f"{API}/problems/{pid}/polygon/sync", json={"dry_run_id": dr["id"], "confirm_problem_id": str(rp["id"])})
    run = api.get(f"{API}/problems/{pid}/polygon/runs/{r.json()['id']}").json()
    assert run["status"] == "completed", run["result"]
    assert any("ambiguous" in (o.get("detail") or "") for o in run["result"]["operations"])
    assert len(fake.problems[rp["id"]]["tests"]) == 2 and [m for m, _ in fake.calls].count("problem.saveTest") == 2


# ── commit / build ───────────────────────────────────────────────────────────
def test_commit_requires_confirmation_and_records_revision(api, fake, local_problem):
    pid = local_problem.id
    rp = _link(api, fake, pid)
    fake.problems[rp["id"]]["modified"] = True
    assert api.post(f"{API}/problems/{pid}/polygon/commit", json={"message": "x"}).status_code == 422
    assert api.post(f"{API}/problems/{pid}/polygon/commit",
                    json={"confirm_problem_id": "1", "message": "PolyPilot sync"}).status_code == 422
    r = api.post(f"{API}/problems/{pid}/polygon/commit",
                 json={"confirm_problem_id": str(rp["id"]), "message": "PolyPilot sync"}).json()
    assert r["committed"] is True and r["revision_before"] == 1 and r["revision_after"] == 2
    r = api.post(f"{API}/problems/{pid}/polygon/commit",
                 json={"confirm_problem_id": str(rp["id"]), "message": "again"}).json()
    assert r["committed"] is False and r["message"] == "No changes"


def test_ambiguous_commit_reconciled(api, fake, local_problem):
    rp = _link(api, fake, local_problem.id)
    fake.problems[rp["id"]]["modified"] = True
    fake.fail["problem.commitChanges"] = "timeout_after_apply"
    r = api.post(f"{API}/problems/{local_problem.id}/polygon/commit",
                 json={"confirm_problem_id": str(rp["id"]), "message": "PolyPilot sync"}).json()
    assert r["committed"] is True and "ambiguous" in r["message"].lower()


def test_build_requires_ack_and_reports_real_state(api, fake, local_problem):
    pid = local_problem.id
    rp = _link(api, fake, pid)
    pf = api.get(f"{API}/problems/{pid}/polygon/build/preflight").json()
    assert pf["ready"] is False and any("Checker is not set" in i for i in pf["issues"])
    r = api.post(f"{API}/problems/{pid}/polygon/build", json={"confirm_problem_id": str(rp["id"])})
    assert r.status_code == 409 and not fake.problems[rp["id"]]["packages"]
    r = api.post(f"{API}/problems/{pid}/polygon/build",
                 json={"confirm_problem_id": str(rp["id"]), "acknowledge_issues": True}).json()
    assert r["state"] == "submitted"                         # accepted request ≠ built
    fake.problems[rp["id"]]["packages"][-1]["state"] = "RUNNING"
    assert api.get(f"{API}/problems/{pid}/polygon/build/status").json()["state"] == "building"
    fake.problems[rp["id"]]["packages"][-1]["state"] = "FAILED"
    assert api.get(f"{API}/problems/{pid}/polygon/build/status").json()["state"] == "failed"
    fake.problems[rp["id"]]["packages"][-1]["state"] = "READY"
    st = api.get(f"{API}/problems/{pid}/polygon/build/status").json()
    assert st["state"] == "built" and st["last_build"]["package_id"] == 1


def test_discard_requires_explicit_text(api, fake, local_problem):
    rp = _link(api, fake, local_problem.id)
    r = api.post(f"{API}/problems/{local_problem.id}/polygon/working-copy/discard",
                 json={"confirm_problem_id": str(rp["id"])})
    assert r.status_code == 422 and not any(m == "problem.discardWorkingCopy" for m, _ in fake.calls)


def test_history_is_persisted(api, fake, local_problem):
    rp = _link(api, fake, local_problem.id)
    api.post(f"{API}/problems/{local_problem.id}/polygon/dry-run", json={})
    runs = api.get(f"{API}/problems/{local_problem.id}/polygon/runs").json()
    assert {r["kind"] for r in runs} == {"dry_run", "link"}
    ov = api.get(f"{API}/problems/{local_problem.id}/polygon").json()
    assert ov["integration"]["external_problem_id"] == str(rp["id"])


def test_failures_only_count_against_the_responsible_artifact(db_session, local_problem):
    """Regression (found by E2E): a stress run failing because of a wrong *candidate* must not mark the
    generator/validator/reference it also compiled as failed."""
    from datetime import datetime, timedelta, timezone
    from app.services.polygon.mapping import Verification
    t0 = datetime.now(timezone.utc)

    def run(test_type, status, kinds=None, failure_kind=None, offset=1):
        comp = {r: {"source_sha256": sha(src)} for r, src in (("gen", GENERATOR), ("val", VALIDATOR),
                                                               ("reference", REFERENCE), ("candidate", BRUTE))}
        rep = {"compilations": comp, "comparison": {"failure_kinds": {k: 1 for k in (kinds or [])}}}
        if failure_kind:
            rep["failure_kind"] = failure_kind
        db_session.add(VerificationRun(problem_id=local_problem.id, test_type=test_type, status=status, report=rep,
                                       created_at=t0 + timedelta(seconds=offset)))
        db_session.commit()

    run("stress", "failed", ["output_mismatch"], offset=10)          # candidate's fault
    run("stress", "failed", failure_kind="infrastructure", offset=11)  # nobody's fault
    v = Verification(db_session, local_problem.id)
    assert v.status(("generate", "differential", "stress"), "gen", sha(GENERATOR))["status"] == "verified"
    assert v.status(("reference",), "reference", sha(REFERENCE))["status"] == "verified"
    run("stress", "failed", ["generator_failure"], offset=12)          # generator's fault
    v = Verification(db_session, local_problem.id)
    assert v.status(("generate", "differential", "stress"), "gen", sha(GENERATOR))["status"] == "failed"
    run("differential", "failed", ["output_mismatch"], offset=13)      # disagreement implicates both solutions
    v = Verification(db_session, local_problem.id)
    assert v.status(("differential",), "candidate", sha(BRUTE))["status"] == "failed"
