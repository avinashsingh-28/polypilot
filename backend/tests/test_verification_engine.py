"""End-to-end engine tests through the real Docker sandbox (skipped if unavailable)."""
import uuid

import pytest

from app.core.config import get_settings
from app.models.artifact import ProblemArtifact
from app.models.counterexample import Counterexample
from app.models.problem import Problem
from app.models.test_case import TestCase
from app.models.verification import VerificationRun
from app.services.sandbox import get_sandbox
from app.services.verification.config import effective_config
from app.services.verification.engine import execute_run
from tests import sandbox_fixtures as F

pytestmark = pytest.mark.sandbox


@pytest.fixture(scope="module", autouse=True)
def require_sandbox():
    try:
        ok = get_sandbox().status()["available"]
    except Exception:
        ok = False
    if not ok:
        pytest.skip("Docker sandbox not available")


@pytest.fixture
def problem(db_session):
    p = Problem(title="Sum", slug=f"sum-{uuid.uuid4().hex[:8]}", time_limit_seconds=1, memory_limit_mb=256)
    db_session.add(p)
    db_session.flush()
    for t, c in (("validator", F.VALIDATOR), ("generator", F.GENERATOR),
                 ("reference_solution", F.REFERENCE), ("brute_force", F.BRUTE)):
        db_session.add(ProblemArtifact(problem_id=p.id, artifact_type=t, content=c, language="cpp"))
    db_session.add(TestCase(problem_id=p.id, test_type="sample", input_data="3\n1 2 3\n", expected_output="6\n"))
    db_session.add(TestCase(problem_id=p.id, test_type="invalid", input_data="11\n1 1 1 1 1 1 1 1 1 1 1\n"))
    db_session.commit()
    return p


def _run(db, problem, test_type, config=None, **kw):
    cfg = effective_config(test_type, config or {}, problem, get_settings())
    run = VerificationRun(problem_id=problem.id, test_type=test_type, status="running", config_params=cfg, **kw)
    db.add(run)
    db.commit()
    return execute_run(db, run)


def _artifact(db, problem, t, content):
    a = ProblemArtifact(problem_id=problem.id, artifact_type=t, content=content, language="cpp")
    db.add(a)
    db.commit()
    return a


def test_compile_run_reports_failure(db_session, problem):
    a = _artifact(db_session, problem, "wa_solution", "int main( {")
    run = _run(db_session, problem, "compile", {"target": {"artifact_id": str(a.id)}})
    assert run.status == "failed" and "Compilation Error" in run.summary
    assert run.report["compilations"]["target"]["status"] == "compilation_error"


def test_validator_accepts_valid_and_rejects_invalid(db_session, problem):
    run = _run(db_session, problem, "validator")
    assert run.status == "passed", run.summary
    v = run.report["validator"]
    assert v["valid_accepted"] == v["valid_total"] >= 1
    assert v["invalid_rejected"] == v["invalid_total"] >= 5
    statuses = {t.test_type: t.validation_status for t in db_session.query(TestCase).filter_by(problem_id=problem.id)}
    assert statuses == {"sample": "valid", "invalid": "invalid"}


def test_validator_that_accepts_everything_fails(db_session, problem):
    art = db_session.query(ProblemArtifact).filter_by(problem_id=problem.id, artifact_type="validator").one()
    art.content = '#include "testlib.h"\nint main(int c,char**v){registerValidation(c,v);}'
    db_session.commit()
    run = _run(db_session, problem, "validator")
    assert run.status == "failed" and "misjudged" in run.summary


def test_generate_validates_and_is_deterministic(db_session, problem):
    run = _run(db_session, problem, "generate", {"count": 4, "seed": 42, "gen_type": "small"})
    assert run.status == "passed", run.summary
    saved = run.report["generator"]["saved"]
    tcs = db_session.query(TestCase).filter_by(problem_id=problem.id, test_type="generated").all()
    assert len(tcs) == len(saved) >= 1 and all(t.validation_status == "valid" for t in tcs)
    assert tcs[0].generation_meta["seed"] in (42, 43, 44, 45)
    run2 = _run(db_session, problem, "generate", {"count": 4, "seed": 42, "gen_type": "small"})
    assert run2.report["generator"]["duplicates"] == len(saved)     # same seeds → identical inputs


def test_reference_on_tests(db_session, problem):
    _run(db_session, problem, "validator")
    run = _run(db_session, problem, "reference", {"save_outputs": True})
    assert run.status == "passed", run.summary
    assert run.report["reference"]["judged"] == 1
    assert run.report["reference"]["results"][0]["status"] == "Accepted"


def test_reference_with_custom_checker(db_session, problem):
    _artifact(db_session, problem, "checker", F.CHECKER)
    run = _run(db_session, problem, "reference")
    assert run.status == "passed", run.summary
    assert run.report["reference"]["checker"] == "testlib checker"


def test_differential_agrees(db_session, problem):
    run = _run(db_session, problem, "differential", {"iterations": 20, "seed": 7})
    assert run.status == "passed", run.summary
    assert run.report["comparison"]["iterations_completed"] == 20


def test_stress_finds_and_minimizes_counterexample(db_session, problem):
    bug = _artifact(db_session, problem, "wa_solution", F.BUGGY)
    run = _run(db_session, problem, "stress", {"iterations": 50, "seed": 1, "candidate": {"artifact_id": str(bug.id)}})
    assert run.status == "failed" and "output mismatch" in run.summary
    cx = db_session.query(Counterexample).filter_by(verification_run_id=run.id).one()
    assert cx.kind == "mismatch" and cx.seed is not None and cx.ref_output.strip() != cx.candidate_output.strip()
    assert cx.details["minimization"]["attempts"] > 0
    if cx.minimized_input:
        assert len(cx.minimized_input) <= len(cx.input_data) and "-" in cx.minimized_input


def test_candidate_wrong_answer_and_tle(db_session, problem):
    bug = _artifact(db_session, problem, "wa_solution", F.BUGGY)
    db_session.add(TestCase(problem_id=problem.id, test_type="manual", input_data="2\n-1 -2\n",
                            expected_output="-3\n", validation_status="valid", is_valid=True))
    db_session.commit()
    run = _run(db_session, problem, "candidate", {"candidate": {"artifact_id": str(bug.id)}, "expected_verdict": "WA"})
    assert run.status == "passed", run.summary
    assert run.report["candidate"]["verdict"] == "WA" and run.report["candidate"]["evidence_counterexample_id"]

    slow = _artifact(db_session, problem, "tle_solution", F.SLOW)
    run = _run(db_session, problem, "candidate", {"candidate": {"artifact_id": str(slow.id)},
                                                  "expected_verdict": "TLE", "tle_confirm_runs": 1,
                                                  "time_limit_sec": 0.5})
    assert run.report["candidate"]["verdict"] == "TLE", run.summary
    assert run.report["candidate"]["results"][0]["tle_confirmed"] is True


def test_cancellation(db_session, problem):
    run = _run(db_session, problem, "differential", {"iterations": 200, "seed": 3}, cancel_requested=True)
    assert run.status == "cancelled"
    assert (run.progress or {}).get("iterations_done", 0) <= 10


def test_missing_artifact_is_reported(db_session, problem):
    db_session.query(ProblemArtifact).filter_by(problem_id=problem.id, artifact_type="brute_force").delete()
    db_session.commit()
    run = _run(db_session, problem, "differential", {"iterations": 5})
    assert run.status == "failed" and "brute_force" in run.summary
