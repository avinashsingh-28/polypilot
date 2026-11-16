"""Phase 6: authentication, authorization (IDOR), CSRF, sessions, health, limits, AI reliability."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app
from app.models.counterexample import Counterexample
from app.models.user import AIUsage, User, UserSession, WorkerHeartbeat
from app.models.verification import VerificationRun
from app.services.ai import TrackedProvider
from app.services.ai.base import AIError
from app.services.ai.gemini import GeminiProvider
from tests.conftest import TEST_EMAIL, TEST_PASSWORD, login_client

API = "/api/v1"


def _second_client(db_session):
    c = TestClient(app)
    login_client(c, "mallory@example.com", "another-strong-pass-7")
    return c


# ── authentication ───────────────────────────────────────────────────────────
def test_register_is_generic_and_never_leaks(anon_client, db_session):
    body = {"email": "Alice@Example.com", "password": "a-very-good-pass-1"}
    r1 = anon_client.post(f"{API}/auth/register", json=body)
    r2 = anon_client.post(f"{API}/auth/register", json=body)          # duplicate
    assert r1.status_code == r2.status_code == 202 and r1.json() == r2.json()
    u = db_session.query(User).filter_by(email="alice@example.com").one()
    assert u.password_hash.startswith("$argon2id$") and "a-very-good-pass-1" not in u.password_hash
    assert "password" not in r1.text.lower().replace("password.", "") or "hash" not in r1.text
    assert anon_client.cookies.get("pp_session") is None                # registration does not log in


@pytest.mark.parametrize("pw", ["short", "aaaaaaaaaaaa", "password123", "alice-secret-1"])
def test_password_policy(anon_client, pw):
    r = anon_client.post(f"{API}/auth/register", json={"email": "alice@example.com", "password": pw})
    assert r.status_code == 422


def test_login_errors_are_generic(anon_client):
    anon_client.post(f"{API}/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    a = anon_client.post(f"{API}/auth/login", json={"email": TEST_EMAIL, "password": "wrong-password-1"})
    b = anon_client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": "wrong-password-1"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()
    assert TEST_PASSWORD not in a.text


def test_session_cookie_flags_and_me(anon_client):
    login_client(anon_client)
    me = anon_client.get(f"{API}/auth/me").json()
    assert me["email"] == TEST_EMAIL and "password_hash" not in me
    # login response sets HttpOnly session cookie and a readable CSRF cookie
    r = anon_client.post(f"{API}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    cookies = r.headers.get_list("set-cookie")
    sess = next(c for c in cookies if c.startswith("pp_session="))
    csrf = next(c for c in cookies if c.startswith("pp_csrf="))
    assert "HttpOnly" in sess and "SameSite=lax" in sess and "HttpOnly" not in csrf


def test_protected_routes_require_auth(anon_client):
    for method, path in (("get", "/problems"), ("post", "/problems"), ("get", "/polygon/status"),
                         ("get", "/sandbox/status"), ("get", "/ai/status")):
        assert getattr(anon_client, method)(f"{API}{path}").status_code == 401, path


def test_csrf_required_for_unsafe_methods(client):
    token = client.headers.pop("X-CSRF-Token")
    assert client.post(f"{API}/problems", json={"title": "x"}).status_code == 403
    client.headers["X-CSRF-Token"] = "forged"
    assert client.post(f"{API}/problems", json={"title": "x"}).status_code == 403
    client.headers["X-CSRF-Token"] = token
    assert client.post(f"{API}/problems", json={"title": "Real"}).status_code == 201
    assert client.get(f"{API}/problems").status_code == 200           # safe methods need no token


def test_logout_revokes_session(client, db_session):
    old = client.cookies.get("pp_session")
    assert client.post(f"{API}/auth/logout").status_code == 200
    client.cookies.set("pp_session", old)
    assert client.get(f"{API}/auth/me").status_code == 401
    assert db_session.query(UserSession).filter(UserSession.revoked_at.isnot(None)).count() >= 1


def test_expired_and_idle_sessions_rejected(client, db_session):
    sess = db_session.query(UserSession).filter_by(revoked_at=None).first()
    sess.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    assert client.get(f"{API}/auth/me").status_code == 401
    sess.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    sess.last_seen_at = datetime.now(timezone.utc) - timedelta(days=3)
    db_session.commit()
    assert client.get(f"{API}/auth/me").status_code == 401


def test_login_rate_limited(anon_client):
    s = get_settings()
    codes = [anon_client.post(f"{API}/auth/login", json={"email": f"x{i}@example.com", "password": "nope-nope-1"}).status_code
             for i in range(s.AUTH_RATE_LIMIT_PER_MIN + 2)]
    assert codes[-1] == 429 and 401 in codes


def test_per_account_failure_lockout(anon_client):
    from app.core.security import limiter
    anon_client.post(f"{API}/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    for _ in range(get_settings().AUTH_MAX_FAILURES_PER_EMAIL):
        anon_client.post(f"{API}/auth/login", json={"email": TEST_EMAIL, "password": "wrong-pass-123"})
    # clear only the per-IP window to isolate the per-account limit
    for k in list(limiter._hits):
        if k.startswith("login:ip:"):
            limiter.reset(k)
    r = anon_client.post(f"{API}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert r.status_code == 429


# ── authorization (IDOR) ─────────────────────────────────────────────────────
def test_users_cannot_access_each_others_data(client, db_session):
    pid = client.post(f"{API}/problems", json={"title": "Private"}).json()["id"]
    art = client.post(f"{API}/problems/{pid}/artifacts", json={"artifact_type": "statement", "content": "secret"}).json()
    tc = client.post(f"{API}/problems/{pid}/test-cases", json={"input_data": "1\n"}).json()
    run = client.post(f"{API}/problems/{pid}/verification-runs", json={"test_type": "validator"}).json()
    cx = Counterexample(problem_id=uuid.UUID(pid), input_data="1", ref_output="1", candidate_output="2")
    db_session.add(cx)
    db_session.commit()

    with TestClient(app) as m:
        login_client(m, "mallory@example.com", "another-strong-pass-7")
        assert m.get(f"{API}/problems").json()["total"] == 0
        for method, path, body in (
            ("get", f"/problems/{pid}", None), ("patch", f"/problems/{pid}", {"title": "pwned"}),
            ("delete", f"/problems/{pid}", None), ("get", f"/problems/{pid}/artifacts", None),
            ("get", f"/artifacts/{art['id']}", None), ("patch", f"/artifacts/{art['id']}", {"content": "x"}),
            ("get", f"/problems/{pid}/test-cases/{tc['id']}", None), ("get", f"/problems/{pid}/test-cases", None),
            ("get", f"/problems/{pid}/verification-runs/{run['id']}", None),
            ("post", f"/problems/{pid}/verification-runs/{run['id']}/cancel", None),
            ("get", f"/problems/{pid}/counterexamples/{cx.id}", None), ("get", f"/problems/{pid}/polygon", None),
            ("post", f"/problems/{pid}/polygon/preview", {}), ("get", f"/problems/{pid}/verification/summary", None),
            ("post", f"/problems/{pid}/generate", None), ("get", f"/problems/{pid}/generation-status", None),
        ):
            kw = {"json": body} if body is not None else {}
            r = getattr(m, method)(f"{API}{path}", **kw)
            assert r.status_code == 404, (method, path, r.status_code)
    assert client.get(f"{API}/problems/{pid}").json()["title"] == "Private"
    assert client.get(f"{API}/artifacts/{art['id']}").json()["content"] == "secret"


def test_polygon_credentials_are_per_user(client, db_session, monkeypatch):
    from cryptography.fernet import Fernet
    s = get_settings()
    for k, v in (("POLYGON_API_KEY", ""), ("POLYGON_API_SECRET", ""), ("POLYGON_CREDENTIALS_KEY", Fernet.generate_key().decode())):
        monkeypatch.setattr(s, k, v)
    assert client.put(f"{API}/polygon/credentials", json={"api_key": "aaaaaaaa11", "api_secret": "bbbbbbbb22"}).json()["configured"]
    with TestClient(app) as m:
        login_client(m, "mallory@example.com", "another-strong-pass-7")
        assert m.get(f"{API}/polygon/status").json()["configured"] is False


def test_env_polygon_credentials_restricted_in_production(monkeypatch, auth_user):
    from app.services.polygon.credentials import env_credentials_allowed
    s = get_settings()
    monkeypatch.setattr(s, "POLYGON_API_KEY", "k" * 10)
    monkeypatch.setattr(s, "POLYGON_API_SECRET", "s" * 10)
    monkeypatch.setattr(s, "ENVIRONMENT", "production")
    monkeypatch.setattr(s, "POLYGON_ENV_CREDENTIALS_EMAIL", "")
    assert env_credentials_allowed(auth_user) is False
    monkeypatch.setattr(s, "POLYGON_ENV_CREDENTIALS_EMAIL", TEST_EMAIL)
    assert env_credentials_allowed(auth_user) is True


# ── HTTP hardening / health ──────────────────────────────────────────────────
def test_security_headers_request_id_and_size_limit(client):
    r = client.get(f"{API}/auth/me")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
    assert len(r.headers["X-Request-ID"]) >= 16
    big = "x" * (get_settings().MAX_REQUEST_BYTES + 10)
    assert client.post(f"{API}/problems", content=big, headers={"Content-Type": "application/json"}).status_code == 413


def test_validation_errors_do_not_echo_values(anon_client):
    r = anon_client.post(f"{API}/auth/login", json={"email": "a@b.co", "password": 12345678901234})
    assert r.status_code == 422 and "12345678901234" not in r.text


def test_unhandled_errors_are_generic(client, monkeypatch):
    import app.api.routes.ai as ai_routes

    def boom(*a, **k):
        raise RuntimeError("internal secret detail")
    monkeypatch.setattr(ai_routes, "calls_today", boom)
    with TestClient(app, raise_server_exceptions=False) as c:
        c.cookies.update(client.cookies)
        r = c.get(f"{API}/ai/status")
    assert r.status_code == 500 and "secret detail" not in r.text and "Traceback" not in r.text


def test_health_endpoints(anon_client, db_session):
    assert anon_client.get("/health").json()["status"] == "ok"
    assert anon_client.get("/health/ready").json()["database"] is True
    r = anon_client.get("/health/worker")
    assert r.status_code == 503 and r.json()["status"] == "no_live_worker"
    db_session.add(WorkerHeartbeat(worker_id="w1", state="idle", sandbox_available=True,
                                   last_seen_at=datetime.now(timezone.utc), jobs_completed=0, jobs_failed=0))
    db_session.commit()
    r = anon_client.get("/health/worker")
    assert r.status_code == 200 and r.json()["workers_alive"] == 1 and r.json()["sandbox_available"] is True
    m = anon_client.get("/metrics")
    assert m.status_code == 200 and "polypilot_http_requests_total" in m.text and "polypilot_workers_alive 1" in m.text


def test_metrics_token(anon_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "METRICS_TOKEN", "t0ken")
    assert anon_client.get("/metrics").status_code == 401
    assert anon_client.get("/metrics", headers={"Authorization": "Bearer t0ken"}).status_code == 200


def test_production_config_validation():
    bad = Settings(_env_file=None, ENVIRONMENT="production", AUTH_SECRET_KEY="short", COOKIE_SECURE=False,
                   CORS_ORIGINS=["*"], DATABASE_URL="sqlite:///x.db")
    errs = bad.production_problems()
    assert len(errs) >= 4
    good = Settings(_env_file=None, ENVIRONMENT="production", AUTH_SECRET_KEY="k" * 40, COOKIE_SECURE=True,
                    CORS_ORIGINS=["https://polypilot.example"], DATABASE_URL="postgresql://u:p@db/x")
    assert good.production_problems() == []


# ── worker recovery ──────────────────────────────────────────────────────────
def test_worker_recovers_stale_running_jobs(client, db_session):
    from app.worker import recover_stale
    pid = client.post(f"{API}/problems", json={"title": "R"}).json()["id"]
    run = VerificationRun(problem_id=uuid.UUID(pid), test_type="stress", status="running",
                          heartbeat_at=datetime.now(timezone.utc) - timedelta(hours=1))
    db_session.add(run)
    db_session.commit()
    assert recover_stale(db_session, 300) >= 1
    db_session.refresh(run)
    assert run.status == "failed" and run.report["failure_kind"] == "infrastructure"


# ── AI provider reliability ──────────────────────────────────────────────────
class _Coded(Exception):
    def __init__(self, code):
        self.code = code


def test_ai_error_classification():
    c = GeminiProvider._classify
    assert c(_Coded(429)).kind == "rate_limited" and c(_Coded(429)).transient
    assert c(_Coded(503)).kind == "unavailable" and c(_Coded(503)).transient
    assert c(_Coded(403)).kind == "auth" and not c(_Coded(403)).transient
    assert c(_Coded(400)).kind == "invalid_request"
    assert c(asyncio.TimeoutError()).kind == "timeout"
    with pytest.raises(AIError) as e:
        GeminiProvider(api_key="")
    assert e.value.kind == "missing_key"


class _Inner:
    name, model = "fake", "fake-1"

    def __init__(self, fail=None):
        self.fail = fail

    async def generate_text(self, prompt, temperature=0.4):
        if self.fail:
            raise self.fail
        return "RESPONSE-CONTENT"

    async def generate_json(self, prompt, temperature=0.2):
        return {"a": 1}


def test_tracked_provider_quota_and_no_content_logged(client, db_session, auth_user):
    t = TrackedProvider(_Inner(), lambda: db_session, auth_user.id, None, "test", daily_limit=2)
    assert asyncio.run(t.generate_text("SECRET-PROMPT")) == "RESPONSE-CONTENT"
    with pytest.raises(AIError):
        asyncio.run(TrackedProvider(_Inner(AIError("timeout", "t")), lambda: db_session, auth_user.id, None, "test", 2)
                    .generate_text("p"))
    with pytest.raises(AIError) as e:
        asyncio.run(t.generate_text("again"))
    assert e.value.kind == "quota_exceeded"
    rows = db_session.query(AIUsage).filter_by(user_id=auth_user.id).all()
    assert {r.status for r in rows} == {"ok", "error"} and rows[0].prompt_chars > 0
    dump = " ".join(str(vars(r)) for r in rows)
    assert "SECRET-PROMPT" not in dump and "RESPONSE-CONTENT" not in dump


# ── Phase 6 (second pass): structured output, queue bounds, safe retry, DB outage ──
def test_specification_structured_output_validation():
    from app.services.generation.steps import validate_specification
    ok = {"problem_name": "A", "legend": "l", "formal_statement": "f", "input_format": "i", "output_format": "o",
          "samples": [{"input": "1", "output": "1"}], "time_limit_seconds": 1, "memory_limit_mb": 256}
    assert validate_specification(ok) is ok
    for bad in ([], {**ok, "samples": []}, {**ok, "problem_name": "a\nb"}, {**ok, "legend": " "},
                {**ok, "memory_limit_mb": 10 ** 6}, {**ok, "samples": [{"input": 1}]}, {**ok, "time_limit_seconds": True}):
        with pytest.raises(AIError) as e:
            validate_specification(bad)
        assert e.value.kind == "invalid_response"


def test_per_user_and_global_queue_bounds(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "MAX_ACTIVE_RUNS_PER_USER", 2)
    pids = [client.post(f"{API}/problems", json={"title": f"Q{i}"}).json()["id"] for i in range(3)]
    assert client.post(f"{API}/problems/{pids[0]}/verification-runs", json={"test_type": "validator"}).status_code == 202
    assert client.post(f"{API}/problems/{pids[1]}/verification-runs", json={"test_type": "validator"}).status_code == 202
    r = client.post(f"{API}/problems/{pids[2]}/verification-runs", json={"test_type": "validator"})
    assert r.status_code == 429 and "active verification runs" in r.json()["detail"]
    monkeypatch.setattr(s, "MAX_ACTIVE_RUNS_PER_USER", 100)
    monkeypatch.setattr(s, "MAX_QUEUED_RUNS_TOTAL", 2)
    assert client.post(f"{API}/problems/{pids[2]}/verification-runs", json={"test_type": "validator"}).status_code == 503


class _DownSandbox:
    def execute(self, *a, **k):
        from app.services.sandbox import SandboxUnavailable
        raise SandboxUnavailable("docker is down")


def test_sandbox_unavailable_is_retried_once_then_failed(client, db_session):
    from app.models.artifact import ProblemArtifact
    from app.services.sandbox.compiler import Compiler
    from app.services.verification.engine import execute_run
    Compiler._cache.clear()
    pid = client.post(f"{API}/problems", json={"title": "Down"}).json()["id"]
    db_session.add(ProblemArtifact(problem_id=uuid.UUID(pid), artifact_type="validator",
                                   content="int main(){/*unique-%s*/}" % uuid.uuid4().hex))
    db_session.add(VerificationRun(problem_id=uuid.UUID(pid), test_type="validator", status="running", config_params={}))
    db_session.commit()
    run = db_session.query(VerificationRun).filter_by(problem_id=uuid.UUID(pid)).one()
    execute_run(db_session, run, sandbox=_DownSandbox())
    assert run.status == "queued" and run.progress["infra_attempts"] == 1      # safe: nothing executed
    run.status = "running"
    execute_run(db_session, run, sandbox=_DownSandbox())
    assert run.status == "failed" and run.report["failure_kind"] == "infrastructure"


def test_database_outage_returns_503(client, monkeypatch):
    from sqlalchemy.exc import OperationalError
    import app.api.routes.ai as ai_routes

    def down(*a, **k):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))
    monkeypatch.setattr(ai_routes, "calls_today", down)
    r = client.get(f"{API}/ai/status")
    assert r.status_code == 503 and "temporarily unavailable" in r.json()["detail"] and "refused" not in r.text
