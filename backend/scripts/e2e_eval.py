"""
PolyPilot end-to-end evaluation.

Runs the real API (in-process), the real PostgreSQL database configured in backend/.env, the real
verification worker code and the real Docker sandbox. AI responses are MOCKED (no paid calls).

Polygon:
  default            mock Polygon server (in-memory fake that checks request signatures)
  --live-polygon-id N  use your real Polygon credentials against a DEDICATED THROWAWAY problem N.
                     Read-only (dry run) unless you also pass:
                       --approve-upload   upload to that problem's working copy
                       --approve-commit   commit the working copy
                       --approve-build    request a package build and poll its real result

Every step reports PASSED / FAILED / SKIPPED / BLOCKED / NOT_IMPLEMENTED. Temporary data
(user + problem) is deleted at the end unless --keep.

    cd backend
    python -m scripts.e2e_eval                    # mock AI + mock Polygon
    python -m scripts.e2e_eval --report e2e.json
"""
import argparse
import json
import os
import sys
import time
import traceback
import uuid
from contextlib import contextmanager
from unittest.mock import patch

os.environ.setdefault("STARTUP_RECOVERY", "false")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services.ai.base import AIProvider  # noqa: E402
from tests import sandbox_fixtures as F  # noqa: E402

API = "/api/v1"
SPEC = {
    "problem_name": "Sum of Integers", "legend": "Little Petya likes adding numbers.",
    "formal_statement": "Given $n$ integers $a_1, \\ldots, a_n$, print their sum.",
    "input_format": "The first line contains $n$ ($1 \\le n \\le 10$). The second line contains $n$ integers "
                    "$a_i$ ($-100 \\le a_i \\le 100$).",
    "output_format": "Print one integer — the sum.",
    "constraints": {"n_max": 10, "other": ["-100 <= a_i <= 100"]},
    "time_limit_seconds": 1, "memory_limit_mb": 256, "intended_algorithm": "Linear scan",
    "complexity": {"time": "O(n)", "space": "O(1)"}, "correctness_reasoning": "Addition.",
    "samples": [{"input": "3\n1 2 3\n", "output": "6\n", "explanation": "1+2+3=6"},
                {"input": "2\n-5 5\n", "output": "0\n", "explanation": "-5+5=0"}],
    "edge_cases": ["n=1", "all negative"], "notes": "",
}
STATEMENT = ("# Sum of Integers\n\nLittle Petya likes adding numbers. Given $n$ integers $a_1, \\ldots, a_n$, "
             "print **their sum**.\n\n## Input\nThe first line contains $n$ ($1 \\le n \\le 10$). The second line "
             "contains $n$ integers $a_i$ ($-100 \\le a_i \\le 100$).\n\n## Output\nPrint one integer — the sum.\n\n"
             "## Examples\n```\n3\n1 2 3\n```\n")
EDITORIAL = "Add all numbers in $O(n)$."


class MockAI(AIProvider):
    """Deterministic stand-in for the Phase 3 provider. Routes on each prompt's role line."""
    name, model = "mock", "mock-1"

    def __init__(self):
        self.calls = 0

    async def generate_json(self, prompt, *, temperature=0.2):
        self.calls += 1
        return SPEC

    async def generate_text(self, prompt, *, temperature=0.4):
        self.calls += 1
        for marker, out in (("official problem statement", STATEMENT), ("reference (accepted)", F.REFERENCE),
                            ("brute-force", F.BRUTE), ("testlib validator", F.VALIDATOR),
                            ("testlib test generator", F.GENERATOR), ("the editorial", EDITORIAL)):
            if marker in prompt:
                return out
        raise AssertionError("MockAI: unrecognized prompt")


class Report:
    def __init__(self):
        self.steps = []

    def add(self, n, name, status, detail=""):
        self.steps.append({"step": n, "name": name, "status": status, "detail": str(detail)[:400]})
        print(f"{n:>2}. {status:<16} {name}" + (f" — {detail}" if detail else ""), flush=True)

    @contextmanager
    def step(self, n, name):
        try:
            box = {"detail": ""}
            yield box
            self.add(n, name, box.get("status", "PASSED"), box["detail"])
        except Exception as e:  # noqa: BLE001
            self.add(n, name, "FAILED", f"{type(e).__name__}: {e}")
            if os.environ.get("E2E_DEBUG"):
                traceback.print_exc()

    def failed(self):
        return [s for s in self.steps if s["status"] == "FAILED"]


def run_worker_until_done(client, pid, run_id, timeout=600):
    from app.worker import process_one
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"{API}/problems/{pid}/verification-runs/{run_id}").json()
        if r["status"] in ("passed", "failed", "cancelled"):
            return r
        process_one()
    raise TimeoutError("verification run did not finish")


def start_run(client, pid, test_type, config=None):
    r = client.post(f"{API}/problems/{pid}/verification-runs", json={"test_type": test_type, "config": config or {}})
    assert r.status_code == 202, r.text
    return run_worker_until_done(client, pid, r.json()["id"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live-polygon-id")
    ap.add_argument("--approve-upload", action="store_true")
    ap.add_argument("--approve-commit", action="store_true")
    ap.add_argument("--approve-build", action="store_true")
    ap.add_argument("--report")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    s = get_settings()
    rep = Report()
    email = f"e2e-{uuid.uuid4().hex[:10]}@example.invalid"
    password = f"E2e-{uuid.uuid4().hex}"
    mock_ai = MockAI()
    pid = None
    live = bool(args.live_polygon_id)
    print(f"PolyPilot E2E — database: PostgreSQL, AI: MOCK, Polygon: {'LIVE #' + args.live_polygon_id if live else 'MOCK'}\n")

    from app.api.routes import polygon as polygon_routes
    from tests.fake_polygon import KEY, SECRET, FakePolygon
    fake = FakePolygon()
    patches = [patch("app.services.generation.pipeline.get_ai_provider", return_value=mock_ai),
               patch.object(s, "GEMINI_API_KEY", s.GEMINI_API_KEY or "mock-key-not-used")]
    if not live:
        patches += [patch.object(s, "POLYGON_API_KEY", KEY), patch.object(s, "POLYGON_API_SECRET", SECRET),
                    patch.object(s, "POLYGON_MIN_INTERVAL_SEC", 0.0)]
        app.dependency_overrides[polygon_routes.get_polygon_transport] = lambda: fake.transport()
    for p in patches:
        p.start()
    try:
        with TestClient(app) as c:
            c.post(f"{API}/auth/register", json={"email": email, "password": password})
            r = c.post(f"{API}/auth/login", json={"email": email, "password": password})
            assert r.status_code == 200, r.text
            c.headers["X-CSRF-Token"] = c.cookies.get("pp_csrf")

            with rep.step(1, "Create problem draft") as b:
                r = c.post(f"{API}/problems", json={"title": "E2E Sum of Integers", "idea": "Sum n integers",
                                                    "time_limit_seconds": 1, "memory_limit_mb": 256})
                assert r.status_code == 201, r.text
                pid = r.json()["id"]
                b["detail"] = pid
            with rep.step(2, "Generate structured specification + all artifacts (mock AI, real pipeline)") as b:
                r = c.post(f"{API}/problems/{pid}/generate")
                assert r.status_code == 202, r.text
                st = c.get(f"{API}/problems/{pid}/generation-status").json()
                assert st["status"] == "completed", st
                b["detail"] = f"{mock_ai.calls} mocked AI calls, 7 pipeline steps"
            arts = {a["artifact_type"]: a for a in c.get(f"{API}/problems/{pid}/artifacts").json()}
            with rep.step(3, "Review and save specification") as b:
                spec = json.loads(arts["specification"]["content"])
                spec["notes"] = "Reviewed by E2E"
                r = c.patch(f"{API}/artifacts/{arts['specification']['id']}", json={"content": json.dumps(spec)})
                assert r.status_code == 200, r.text
            for n, t in ((4, "statement"), (5, "editorial"), (6, "reference_solution"), (7, "brute_force"),
                         (8, "validator"), (9, "generator")):
                with rep.step(n, f"Artifact present: {t}") as b:
                    assert arts.get(t) and arts[t]["content"].strip()
                    b["detail"] = f"{len(arts[t]['content'])} chars"

            rep.add("9a", "Generate custom checker", "NOT_IMPLEMENTED",
                    "Phase 3 generates no checker; outputs are judged by token comparison (a stored testlib "
                    "checker artifact is used when present)")

            with rep.step(10, "Compile reference solution in sandbox") as b:
                r = start_run(c, pid, "compile", {"target": {"artifact_type": "reference_solution"}})
                assert r["status"] == "passed", r["summary"]
                b["detail"] = r["summary"]
            with rep.step(11, "Import samples, generate tests, validate (validator vs valid + invalid inputs)") as b:
                assert len(c.post(f"{API}/problems/{pid}/test-cases/import-samples").json()) == 2
                v = start_run(c, pid, "validator")
                assert v["status"] == "passed", v["summary"]
                g = start_run(c, pid, "generate", {"count": 6, "seed": 11, "gen_type": "small"})
                assert g["status"] == "passed", g["summary"]
                b["detail"] = f"{v['summary']} | {g['summary']}"
            with rep.step(12, "Run reference solution on all tests") as b:
                r = start_run(c, pid, "reference", {"save_outputs": True})
                assert r["status"] == "passed", r["summary"]
                b["detail"] = r["summary"]
            with rep.step(13, "Differential testing (reference vs brute force)") as b:
                r = start_run(c, pid, "differential", {"iterations": 30, "seed": 5})
                assert r["status"] == "passed", r["summary"]
                b["detail"] = r["summary"]
            with rep.step(14, "Deliberately wrong candidate is classified WA") as b:
                art = c.post(f"{API}/problems/{pid}/artifacts", json={"artifact_type": "wa_solution", "content": F.BUGGY,
                                                                      "language": "cpp"}).json()
                c.post(f"{API}/problems/{pid}/test-cases", json={"input_data": "2\n-1 -2\n", "expected_output": "-3\n"})
                start_run(c, pid, "validator")
                r = start_run(c, pid, "candidate", {"candidate": {"artifact_id": art["id"]}, "expected_verdict": "WA"})
                assert r["status"] == "passed", r["summary"]
                b["detail"] = r["summary"]
            with rep.step(15, "Deliberately slow candidate is classified TLE (confirmed by re-runs)") as b:
                art = c.post(f"{API}/problems/{pid}/artifacts", json={"artifact_type": "tle_solution", "content": F.SLOW,
                                                                      "language": "cpp"}).json()
                r = start_run(c, pid, "candidate", {"candidate": {"artifact_id": art["id"]}, "expected_verdict": "TLE",
                                                    "time_limit_sec": 0.5, "tle_confirm_runs": 1})
                assert r["status"] == "passed", r["summary"]
                b["detail"] = r["summary"]
            with rep.step("15a", "Capture and minimize a counterexample (stress: reference vs wrong candidate)") as b:
                wa = next(a for a in c.get(f"{API}/problems/{pid}/artifacts").json() if a["artifact_type"] == "wa_solution")
                r = start_run(c, pid, "stress", {"iterations": 60, "seed": 1, "candidate": {"artifact_id": wa["id"]}})
                assert r["status"] == "failed" and "mismatch" in r["summary"], r["summary"]
                cx = [x for x in c.get(f"{API}/problems/{pid}/counterexamples").json() if x["verification_run_id"] == r["id"]]
                assert cx, "no counterexample stored"
                m = cx[0]["details"].get("minimization") or {}
                assert cx[0]["ref_output"].strip() != cx[0]["candidate_output"].strip()
                b["detail"] = (f"seed {cx[0]['seed']}: {cx[0]['input_data']!r} -> minimized "
                               f"{cx[0]['minimized_input']!r} ({m.get('reductions', 0)} validator-checked reductions)")

            with rep.step(16, "Verification results persisted") as b:
                runs = c.get(f"{API}/problems/{pid}/verification-runs?limit=50").json()
                assert len(runs) >= 9 and all(x["status"] in ("passed", "failed") for x in runs)
                b["detail"] = f"{len(runs)} runs stored"

            # ── Polygon ──
            with rep.step(17, "Prepare Polygon package (local preview, no network)") as b:
                pv = c.post(f"{API}/problems/{pid}/polygon/preview", json={}).json()
                blocked = [i for i in pv["items"] if i["action"] == "blocked"]
                assert not blocked, blocked
                b["detail"] = f"{len(pv['items'])} items ready"
            if live:
                polygon_id = args.live_polygon_id
                remote = c.get(f"{API}/polygon/problems").json()
                match = [p for p in remote if str(p["id"]) == str(polygon_id)]
                if not match:
                    for n in range(18, 24):
                        rep.add(n, "Polygon live step", "BLOCKED", "problem id not accessible / credentials missing")
                    raise SystemExit
                r = c.post(f"{API}/problems/{pid}/polygon/link", json={"polygon_problem_id": polygon_id,
                                                                        "confirm_name": match[0]["name"]})
                assert r.status_code == 200, r.text
            else:
                rp = fake.add_problem("e2e-sum")
                polygon_id = str(rp["id"])
                r = c.post(f"{API}/problems/{pid}/polygon/link", json={"polygon_problem_id": polygon_id, "confirm_name": "e2e-sum"})
                assert r.status_code == 200, r.text
            tag = "" if live else " (mock Polygon)"
            dry = None
            with rep.step(18, "Preview synchronization (dry run: reads only)" + tag) as b:
                dry = c.post(f"{API}/problems/{pid}/polygon/dry-run", json={}).json()
                b["detail"] = dry["summary"]
            if live and not args.approve_upload:
                rep.add(19, "Synchronize to dedicated test problem", "BLOCKED", "needs --approve-upload")
                rep.add(20, "Verify uploaded files", "SKIPPED", "no upload performed")
            else:
                with rep.step(19, "Synchronize to dedicated test problem" + tag) as b:
                    r = c.post(f"{API}/problems/{pid}/polygon/sync", json={"dry_run_id": dry["id"],
                                                                            "confirm_problem_id": polygon_id})
                    assert r.status_code == 202, r.text
                    rid, deadline = r.json()["id"], time.time() + 600
                    while time.time() < deadline:
                        run = c.get(f"{API}/problems/{pid}/polygon/runs/{rid}").json()
                        if run["status"] not in ("planned", "running"):
                            break
                        time.sleep(1)
                    assert run["status"] == "completed", run["summary"]
                    b["detail"] = run["summary"]
                with rep.step(20, "Verify uploaded files (read back from Polygon)" + tag) as b:
                    dry2 = c.post(f"{API}/problems/{pid}/polygon/dry-run", json={}).json()
                    pending = [i["key"] for i in dry2["plan"]["items"] if i["action"] not in ("unchanged",)]
                    assert not pending, pending
                    b["detail"] = "all items unchanged after upload (remote matches local)"
            if live and not args.approve_commit:
                rep.add(21, "Commit (explicit approval)", "BLOCKED", "needs --approve-commit")
            else:
                with rep.step(21, "Commit (explicit approval)" + tag) as b:
                    r = c.post(f"{API}/problems/{pid}/polygon/commit", json={"confirm_problem_id": polygon_id,
                                                                              "message": "PolyPilot E2E evaluation"}).json()
                    assert r["committed"] is True, r
                    b["detail"] = f"revision {r['revision_before']} -> {r['revision_after']}"
            if live and not args.approve_build:
                rep.add(22, "Trigger package build (explicit approval)", "BLOCKED", "needs --approve-build")
                rep.add(23, "Verify actual package build result", "SKIPPED", "no build requested")
            else:
                with rep.step(22, "Trigger package build (explicit approval)" + tag) as b:
                    r = c.post(f"{API}/problems/{pid}/polygon/build", json={"confirm_problem_id": polygon_id,
                                                                             "acknowledge_issues": True, "verify": True})
                    assert r.status_code == 200, r.text
                    b["detail"] = f"request {r.json()['last_build']['request_status']}"
                with rep.step(23, "Verify actual package build result" + tag) as b:
                    deadline = time.time() + (900 if live else 5)
                    state = "unknown"
                    while time.time() < deadline:
                        if not live and fake.problems[int(polygon_id)]["packages"]:
                            fake.problems[int(polygon_id)]["packages"][-1]["state"] = "READY"   # mock builder
                        state = c.get(f"{API}/problems/{pid}/polygon/build/status").json()["state"]
                        if state in ("built", "failed"):
                            break
                        time.sleep(10 if live else 0.2)
                    assert state == "built", f"package state: {state}"
                    b["detail"] = "Polygon reports package READY" + (" (mock builder)" if not live else "")
    except SystemExit:
        pass
    finally:
        for p in patches:
            p.stop()
        app.dependency_overrides.clear()
        if not args.keep:
            with SessionLocal() as db:
                if pid:
                    db.execute(text("DELETE FROM problems WHERE id = :p"), {"p": pid})
                db.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
                db.commit()
            print("\ncleanup: temporary user and problem deleted")

    summary = {k: sum(1 for x in rep.steps if x["status"] == k) for k in
               ("PASSED", "FAILED", "SKIPPED", "BLOCKED", "NOT_IMPLEMENTED")}
    print("summary:", summary)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump({"polygon": "live" if live else "mock", "ai": "mock", "steps": rep.steps, "summary": summary}, f, indent=2)
    return 1 if rep.failed() or len(rep.steps) < 25 else 0


if __name__ == "__main__":
    sys.exit(main())
