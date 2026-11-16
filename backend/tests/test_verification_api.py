"""API + pure-logic tests for Phase 4 (no Docker, no paid AI calls)."""
import json
import uuid
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.models.artifact import ProblemArtifact
from app.models.counterexample import Counterexample
from app.models.verification import VerificationRun
from app.services.sandbox.comparator import TokenComparator
from app.services.verification.config import ConfigError, effective_config
from app.services.verification.engine import mutate, strip_fences
from app.services.verification.minimizer import shrink_array, shrink_numbers

API = "/api/v1"


def _problem(client, title="Sum"):
    r = client.post(f"{API}/problems", json={"title": title, "time_limit_seconds": 1.0, "memory_limit_mb": 256})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── comparator ──
def test_token_comparator_whitespace_and_exactness():
    c = TokenComparator()
    assert c.compare("1 2\n3  \n\n", "1\n2 3").matched
    assert not c.compare("1000001", "1000000").matched          # integers stay exact
    assert not c.compare("1 2", "1 2 3").matched
    assert not c.compare("YES", "yes").matched


def test_token_comparator_float_mode():
    c = TokenComparator(1e-6)
    assert c.compare("0.3333333", "0.33333331").matched
    assert not c.compare("0.34", "0.33").matched
    assert not c.compare("1000001", "1000000").matched          # integer tokens still exact


# ── config clamping ──
class P:
    time_limit_seconds = 2
    memory_limit_mb = 256


def test_config_clamps_to_server_maximum():
    s = get_settings()
    cfg = effective_config("stress", {"iterations": 10**9, "time_limit_sec": 999, "memory_mb": 10**6,
                                      "candidate": {"source": "x", "language": "cpp"}}, P, s)
    assert cfg["iterations"] == s.MAX_STRESS_ITERATIONS
    assert cfg["time_limit_sec"] == s.MAX_TIME_LIMIT_SEC and cfg["memory_mb"] == s.MAX_MEMORY_MB


def test_config_rejects_unsafe_generator_args():
    with pytest.raises(ConfigError):
        effective_config("generate", {"extra_args": ["; rm -rf /"]}, P, get_settings())
    with pytest.raises(ConfigError):
        effective_config("shell", {}, P, get_settings())


def test_mutations_and_minimizer_strategies():
    m = mutate("3\n1 2 3\n")
    assert m["empty_input"] == "" and m["extra_token"].endswith("7\n")
    assert m["overflow_first_integer"].startswith("100000000000000000000")
    assert "4\n" not in list(shrink_array("3\n1 2 3\n"))
    assert "2\n1 2\n" in list(shrink_array("3\n1 2 3\n"))
    assert "0\n" in list(shrink_numbers("5\n"))
    assert strip_fences("```cpp\nint main(){}\n```") == ("int main(){}", True)


# ── test cases ──
def test_test_case_crud_and_limits(client):
    pid = _problem(client)
    r = client.post(f"{API}/problems/{pid}/test-cases", json={"input_data": "3\r\n1 2 3\r\n", "expected_output": "6"})
    assert r.status_code == 201
    tc = r.json()
    assert tc["input_data"] == "3\n1 2 3\n" and tc["validation_status"] == "unchecked" and tc["is_valid"] is False
    assert client.get(f"{API}/problems/{pid}/test-cases").json()[0]["id"] == tc["id"]
    big = "1" * (get_settings().MAX_INPUT_BYTES + 1)
    assert client.post(f"{API}/problems/{pid}/test-cases", json={"input_data": big}).status_code == 413
    assert client.post(f"{API}/problems/{pid}/test-cases", json={"input_data": "a\x00"}).status_code == 422
    assert client.post(f"{API}/problems/{pid}/test-cases", json={"input_data": "1", "test_type": "generated"}).status_code == 422
    # cross-problem isolation
    other = _problem(client, "Other")
    assert client.get(f"{API}/problems/{other}/test-cases/{tc['id']}").status_code == 404
    assert client.delete(f"{API}/problems/{other}/test-cases/{tc['id']}").status_code == 404
    assert client.delete(f"{API}/problems/{pid}/test-cases/{tc['id']}").status_code == 204


def test_import_samples(client, db_session):
    pid = _problem(client)
    db_session.add(ProblemArtifact(problem_id=uuid.UUID(pid), artifact_type="specification",
                                   content=json.dumps({"samples": [{"input": "2\n1 2", "output": "3"}]})))
    db_session.commit()
    r = client.post(f"{API}/problems/{pid}/test-cases/import-samples")
    assert r.status_code == 200 and len(r.json()) == 1 and r.json()[0]["test_type"] == "sample"
    assert client.post(f"{API}/problems/{pid}/test-cases/import-samples").json() == []   # deduplicated


# ── runs ──
def test_create_run_idempotent_and_cancel(client):
    pid = _problem(client)
    body = {"test_type": "validator", "config": {}, "idempotency_key": "abc-1"}
    r1 = client.post(f"{API}/problems/{pid}/verification-runs", json=body)
    r2 = client.post(f"{API}/problems/{pid}/verification-runs", json=body)
    assert r1.status_code == 202 and r1.json()["id"] == r2.json()["id"] and r1.json()["status"] == "queued"
    rid = r1.json()["id"]
    c = client.post(f"{API}/problems/{pid}/verification-runs/{rid}/cancel").json()
    assert c["status"] == "cancelled" and c["cancel_requested"] is True
    other = _problem(client, "Other")
    assert client.get(f"{API}/problems/{other}/verification-runs/{rid}").status_code == 404


def test_run_validation_errors_and_active_limit(client):
    pid = _problem(client)
    assert client.post(f"{API}/problems/{pid}/verification-runs", json={"test_type": "exec_shell"}).status_code == 422
    # artifact from another problem is rejected
    other = _problem(client, "Other")
    art = client.post(f"{API}/problems/{other}/artifacts",
                      json={"artifact_type": "reference_solution", "content": "int main(){}"}).json()
    r = client.post(f"{API}/problems/{pid}/verification-runs",
                    json={"test_type": "compile", "config": {"target": {"artifact_id": art["id"]}}})
    assert r.status_code == 404
    for _ in range(get_settings().MAX_ACTIVE_RUNS_PER_PROBLEM):
        assert client.post(f"{API}/problems/{pid}/verification-runs", json={"test_type": "validator"}).status_code == 202
    assert client.post(f"{API}/problems/{pid}/verification-runs", json={"test_type": "validator"}).status_code == 429


def test_summary(client):
    pid = _problem(client)
    s = client.get(f"{API}/problems/{pid}/verification/summary").json()
    assert s["latest_by_type"]["stress"] is None and s["test_case_counts"]["total"] == 0


def test_worker_claims_queued_run(client, db_session):
    from app.worker import claim_next
    pid = _problem(client)
    rid = client.post(f"{API}/problems/{pid}/verification-runs", json={"test_type": "validator"}).json()["id"]
    run = claim_next(db_session)
    assert run is not None and str(run.id) == rid and run.status == "running"
    assert claim_next(db_session) is None


# ── AI repair (mocked provider; no network) ──
class FakeAI:
    def __init__(self):
        self.calls = 0

    async def generate_text(self, prompt, *, temperature=0.4):
        raise AssertionError("not used")

    async def generate_json(self, prompt, *, temperature=0.2):
        self.calls += 1
        assert "Failing input" in prompt and "5\n" in prompt
        return {"suspected_bug": "abs() applied", "explanation": "remove abs", "code": "```cpp\nint main(){}\n```"}


def test_repair_propose_accept_flow(client, db_session):
    pid = _problem(client)
    art = client.post(f"{API}/problems/{pid}/artifacts",
                      json={"artifact_type": "candidate_solution", "content": "int main(){return 1;}"}).json()
    cx = Counterexample(problem_id=uuid.UUID(pid), input_data="5\n", ref_output="1", candidate_output="2",
                        kind="mismatch", details={"message": "Token #1 differs"})
    db_session.add(cx)
    db_session.commit()
    fake = FakeAI()
    with patch.object(get_settings(), "GEMINI_API_KEY", "test-key"), \
            patch("app.services.ai.get_ai_provider", return_value=fake):
        r = client.post(f"{API}/problems/{pid}/repairs", json={"counterexample_id": str(cx.id), "artifact_id": art["id"]})
    assert r.status_code == 201, r.text
    rep = r.json()
    assert fake.calls == 1 and rep["status"] == "proposed" and rep["repaired_code"] == "int main(){}"
    assert rep["original_code"] == "int main(){return 1;}" and rep["version"] == 1
    # original artifact untouched
    assert client.get(f"{API}/artifacts/{art['id']}").json()["content"] == "int main(){return 1;}"
    acc = client.post(f"{API}/problems/{pid}/repairs/{rep['id']}/accept").json()
    assert acc["status"] == "accepted" and acc["retest_run_id"]
    run = db_session.get(VerificationRun, uuid.UUID(acc["retest_run_id"]))
    assert run.test_type == "candidate" and run.config_params["candidate"]["repair_id"] == rep["id"]
    assert run.config_params["counterexample_id"] == str(cx.id)
    # accepting twice does not queue a duplicate run
    assert client.post(f"{API}/problems/{pid}/repairs/{rep['id']}/accept").json()["retest_run_id"] == acc["retest_run_id"]
    assert client.post(f"{API}/problems/{pid}/repairs/{rep['id']}/reject").status_code == 409


def test_repair_without_ai_provider(client, db_session):
    pid = _problem(client)
    cx = Counterexample(problem_id=uuid.UUID(pid), input_data="1", ref_output="1", candidate_output="2")
    db_session.add(cx)
    db_session.commit()
    with patch.object(get_settings(), "GEMINI_API_KEY", ""):
        r = client.post(f"{API}/problems/{pid}/repairs", json={"counterexample_id": str(cx.id)})
    assert r.status_code == 503
    assert client.get(f"{API}/problems/{pid}/counterexamples/{cx.id}").status_code == 200
