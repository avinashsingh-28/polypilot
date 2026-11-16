"""
Verification engine — executed ONLY by the worker process (app/worker.py).

Every compile/execute goes through the Docker sandbox. This module decides
what to run, interprets sandbox results, and persists evidence.
"""
import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.artifact import ProblemArtifact
from app.models.counterexample import Counterexample
from app.models.problem import Problem
from app.models.solution_repair import SolutionRepair
from app.models.test_case import TestCase
from app.models.verification import VerificationRun
from app.services.sandbox import (
    Bundle, Compiler, CompilationResult, DockerSandbox, Executable, Step, StepResult,
    SandboxInfraError, SandboxUnavailable, apply_checker, classify, get_sandbox, judge_tokens,
)
from app.services.sandbox import runner as R
from app.services.verification.minimizer import minimize

logger = logging.getLogger(__name__)
BATCH = 10
FENCE_RE = re.compile(r"^\s*```[A-Za-z0-9+#]*\s*\n(.*?)\n\s*```\s*$", re.S)


class Cancelled(Exception):
    pass


class JobFailure(Exception):
    """Expected failure of the artifact under test (not infrastructure)."""

    def __init__(self, summary: str, report: Optional[dict] = None):
        super().__init__(summary)
        self.summary = summary
        self.report = report or {}


def _now():
    return datetime.now(timezone.utc)


def strip_fences(code: str) -> Tuple[str, bool]:
    m = FENCE_RE.match(code or "")
    return (m.group(1), True) if m else (code or "", False)


def _decode(b: bytes) -> str:
    return b.decode("utf-8", "replace")


# ─────────────────────────────────────────────────────────────────────────────
class RunContext:
    def __init__(self, db: Session, run: VerificationRun, sandbox: Optional[DockerSandbox] = None):
        self.db = db
        self.run = run
        self.settings = get_settings()
        self.sandbox = sandbox or get_sandbox()
        self.compiler = Compiler(self.sandbox)
        self.problem: Problem = db.get(Problem, run.problem_id)
        self.cfg: dict = run.config_params or {}
        self.deadline = time.monotonic() + int(self.cfg.get("max_seconds", self.settings.MAX_JOB_DURATION_SEC))
        self._log: List[str] = []
        self.report: dict = {"compilations": {}}

    # ── bookkeeping ──
    def log(self, msg: str) -> None:
        line = f"[{_now().strftime('%H:%M:%S')}] {msg}"
        self._log.append(line)
        text = "\n".join(self._log)
        if len(text) > self.settings.MAX_LOG_BYTES:
            text = "…(truncated)\n" + text[-self.settings.MAX_LOG_BYTES:]
        self.run.logs = text

    def progress(self, **kw) -> None:
        self.run.progress = {**(self.run.progress or {}), **kw}
        self.run.heartbeat_at = _now()
        self.db.commit()
        self.db.refresh(self.run, attribute_names=["cancel_requested"])
        if self.run.cancel_requested:
            raise Cancelled()

    def time_left(self) -> bool:
        return time.monotonic() < self.deadline

    # ── artifact resolution (always scoped to this problem) ──
    def artifact(self, artifact_type: str) -> Optional[ProblemArtifact]:
        return (self.db.query(ProblemArtifact)
                .filter_by(problem_id=self.problem.id, artifact_type=artifact_type)
                .order_by(ProblemArtifact.version.desc()).first())

    def resolve(self, spec: dict) -> Tuple[str, str, str]:
        """Return (source, language, label) for a source spec; raises JobFailure if missing."""
        if spec.get("repair_id"):
            rep = self.db.query(SolutionRepair).filter_by(
                id=uuid.UUID(spec["repair_id"]), problem_id=self.problem.id).first()
            if not rep:
                raise JobFailure("Repair not found for this problem")
            return rep.repaired_code, rep.language, f"repair v{rep.version}"
        if spec.get("artifact_id"):
            art = self.db.query(ProblemArtifact).filter_by(
                id=uuid.UUID(spec["artifact_id"]), problem_id=self.problem.id).first()
        elif spec.get("artifact_type"):
            art = self.artifact(spec["artifact_type"])
        else:
            return spec["source"], spec.get("language") or "cpp", spec.get("label", "inline source")
        if not art or not (art.content or "").strip():
            what = spec.get("artifact_type") or spec.get("artifact_id")
            raise JobFailure(f"Artifact '{what}' is missing or empty for this problem")
        src, stripped = strip_fences(art.content)
        if stripped:
            self.log(f"Stripped markdown code fences from {art.artifact_type} (stored artifact unchanged)")
        return src, art.language or self.problem.language or "cpp", f"{art.artifact_type} v{art.version}"

    def compile(self, role: str, source: str, language: str, label: str) -> Executable:
        self.log(f"Compiling {role} ({label}, {language})")
        res: CompilationResult = self.compiler.compile(source, language)
        self.report["compilations"][role] = {**res.to_dict(), "label": label,
                                             "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest()}
        self.db.commit()
        if res.status == "internal_error":
            raise SandboxInfraError(res.error or "compilation infrastructure error")
        if not res.success:
            raise JobFailure(f"Compilation Error in {role} ({label}): {res.error}",
                             {"failed_stage": "compile", "role": role})
        self.log(f"Compiled {role} in {res.duration_ms} ms{' (cached)' if res.cached else ''}")
        return res.executable

    def compile_spec(self, role: str, spec: dict) -> Executable:
        return self.compile(role, *self.resolve(spec))

    def compile_artifact(self, role: str, artifact_type: str, required: bool = True) -> Optional[Executable]:
        art = self.artifact(artifact_type)
        if not art or not (art.content or "").strip():
            if required:
                raise JobFailure(f"No '{artifact_type}' artifact exists for this problem",
                                 {"failed_stage": "missing_artifact", "artifact_type": artifact_type})
            return None
        return self.compile_spec(role, {"artifact_type": artifact_type})

    def checker(self) -> Optional[Executable]:
        art = self.artifact("checker")
        if art and "registerTestlibCmd" in (art.content or ""):
            return self.compile_artifact("checker", "checker")
        return None

    # ── limits ──
    @property
    def tl(self) -> float:
        return float(self.cfg.get("time_limit_sec", 2.0))

    @property
    def mem(self) -> int:
        return int(self.cfg.get("memory_mb", 256))

    @property
    def out_limit(self) -> int:
        return int(self.cfg.get("output_limit_bytes", self.settings.MAX_OUTPUT_BYTES))

    def aux_step(self, sid, cmd, **kw) -> Step:
        """Step for trusted-role tools (validator/generator/checker) with fixed generous limits."""
        return Step(sid, cmd, time_limit=kw.pop("time_limit", 10.0), memory_mb=kw.pop("memory_mb", 512),
                    output_limit=kw.pop("output_limit", self.settings.MAX_INPUT_BYTES + 1), **kw)

    def sol_step(self, sid, cmd, **kw) -> Step:
        return Step(sid, cmd, time_limit=self.tl, memory_mb=self.mem, output_limit=self.out_limit, **kw)

    def judge(self, res, expected: Optional[str], chk_step: Optional[StepResult]):
        if chk_step is not None:
            return apply_checker(res, chk_step)
        if expected is not None:
            return judge_tokens(res, expected, self.cfg.get("float_tolerance"))
        return res


# ─────────────────────────────────────────────────────────────────────────────
# Validator
MUTATIONS = ("empty_input", "extra_token", "missing_last_token", "overflow_first_integer", "non_numeric_first_integer")
_INT = re.compile(r"^[+-]?\d+$")


def mutate(base: str) -> Dict[str, str]:
    """Inputs that are invalid for virtually every CP format (heuristic)."""
    toks = base.split()
    out = {"empty_input": "", "extra_token": base.rstrip("\n") + " 7\n"}
    if len(toks) >= 1:
        idx = base.rstrip().rfind(toks[-1])
        out["missing_last_token"] = base[:idx].rstrip(" ") + ("\n" if not base[:idx].endswith("\n") else "")
    m = re.search(r"(?<![\w.])[+-]?\d+(?![\w.])", base)
    if m:
        out["overflow_first_integer"] = base[:m.start()] + "100000000000000000000" + base[m.end():]
        out["non_numeric_first_integer"] = base[:m.start()] + "abc" + base[m.end():]
    return out


def run_validator(ctx: RunContext) -> Tuple[str, str]:
    val = ctx.compile_artifact("validator", "validator")
    validator_sha = ctx.report["compilations"]["validator"]["source_sha256"]
    tests = ctx.db.query(TestCase).filter_by(problem_id=ctx.problem.id).order_by(TestCase.created_at).all()
    cases = []  # (label, input, expect_valid, test_case or None)
    for tc in tests:
        cases.append((f"test {str(tc.id)[:8]} ({tc.test_type})", tc.input_data, tc.test_type != "invalid", tc))
    valid_bases = [c[1] for c in cases if c[2]]
    if not valid_bases:
        raise JobFailure("No test inputs available to validate. Import samples or add a manual test first.",
                         {"failed_stage": "no_inputs"})
    if ctx.cfg.get("include_mutations", True):
        for name, inp in mutate(valid_bases[0]).items():
            cases.append((f"mutation: {name}", inp, False, None))

    results = []
    b = Bundle().add("val", val)
    for start in range(0, len(cases), 20):
        chunk = cases[start:start + 20]
        steps = [ctx.aux_step(f"v{i}", b.cmd("val"), stdin=c[1].encode()) for i, c in enumerate(chunk)]
        res = ctx.sandbox.execute(b.files, steps, b.exec)
        for (label, inp, expect_valid, tc), r in zip(chunk, res):
            if r.timed_out or r.memory_exceeded or r.spawn_error or r.signal:
                verdict, accepted = "error", None
            else:
                accepted = r.exit_code == 0
                verdict = "accepted" if accepted else "rejected"
            diag = _decode(r.stderr).strip()[:500]
            ok = accepted is not None and accepted == expect_valid
            results.append({"label": label, "expected": "valid" if expect_valid else "invalid",
                            "verdict": verdict, "correct": ok, "exit_code": r.exit_code,
                            "diagnostics": diag, "input_preview": inp[:200],
                            "test_case_id": str(tc.id) if tc else None})
            if tc is not None:
                tc.validation_status = {"accepted": "valid", "rejected": "invalid"}.get(verdict, "error")
                tc.is_valid = verdict == "accepted"
                tc.validation_feedback = diag or ("OK" if accepted else f"exit {r.exit_code}")
                # Bind the verdict to this exact validator source (Polygon upload requires a match).
                tc.generation_meta = {**(tc.generation_meta or {}), "validated_by_sha": validator_sha}
        ctx.progress(iterations_done=len(results), iterations_total=len(cases))

    ctx.report["validator"] = {"cases": results,
                               "valid_accepted": sum(1 for r in results if r["expected"] == "valid" and r["correct"]),
                               "valid_total": sum(1 for r in results if r["expected"] == "valid"),
                               "invalid_rejected": sum(1 for r in results if r["expected"] == "invalid" and r["correct"]),
                               "invalid_total": sum(1 for r in results if r["expected"] == "invalid"),
                               "note": "Mutation inputs are heuristically invalid; review any 'accepted' mutation manually."}
    bad = [r for r in results if not r["correct"]]
    if bad:
        return "failed", f"Validator misjudged {len(bad)}/{len(results)} inputs (first: {bad[0]['label']} → {bad[0]['verdict']})"
    return "passed", f"Validator accepted all {ctx.report['validator']['valid_total']} valid inputs and rejected all {ctx.report['validator']['invalid_total']} invalid inputs"


# ─────────────────────────────────────────────────────────────────────────────
# Generator
def _gen_cmd(b: Bundle, gen_type: str, seed: int, args: List[str]) -> List[str]:
    return b.cmd("gen", gen_type, str(seed), *args)


def run_generate(ctx: RunContext) -> Tuple[str, str]:
    gen = ctx.compile_artifact("gen", "generator")
    val = ctx.compile_artifact("val", "validator")
    b = Bundle().add("gen", gen).add("val", val)
    gen_art, val_art = ctx.artifact("generator"), ctx.artifact("validator")
    cfg = ctx.cfg
    count, seed0, gtype, args = cfg["count"], cfg["seed"], cfg["gen_type"], cfg["extra_args"]
    existing = {hashlib.sha256(t.input_data.encode()).hexdigest()
                for t in ctx.db.query(TestCase.input_data).filter_by(problem_id=ctx.problem.id)}
    saved, invalid, failures, oversized, dupes = [], [], [], [], 0
    for start in range(0, count, BATCH):
        if not ctx.time_left():
            ctx.log("Time budget exhausted")
            break
        seeds = [seed0 + i for i in range(start, min(count, start + BATCH))]
        steps = []
        for sd in seeds:
            steps.append(ctx.aux_step(f"g{sd}", _gen_cmd(b, gtype, sd, args)))
            steps.append(ctx.aux_step(f"v{sd}", b.cmd("val"), stdin={"from": f"g{sd}"}, requires=[f"g{sd}"]))
        res = {r.id: r for r in ctx.sandbox.execute(b.files, steps, b.exec)}
        for sd in seeds:
            g, v = res[f"g{sd}"], res[f"v{sd}"]
            cmd = " ".join(["gen", gtype, str(sd), *args])
            if g.output_exceeded and g.exit_code in (None, 0) and not g.timed_out and not g.memory_exceeded:
                # Larger than PolyPilot's storage limit: a PolyPilot limit, not a generator bug.
                oversized.append({"seed": sd, "cmd": cmd,
                                  "detail": f"output larger than MAX_INPUT_BYTES ({ctx.settings.MAX_INPUT_BYTES} bytes); not stored"})
                continue
            if not g.clean_exit:
                why = classify(g, 10.0, 512).error_details
                failures.append({"seed": sd, "cmd": cmd, "error": why, "stderr": _decode(g.stderr)[:500]})
                continue
            inp = _decode(g.stdout)
            if v.exit_code != 0 or not v.clean_exit:
                invalid.append({"seed": sd, "cmd": cmd, "diagnostics": _decode(v.stderr)[:500],
                                "input_preview": inp[:200]})
                continue
            h = hashlib.sha256(inp.encode()).hexdigest()
            if h in existing:
                dupes += 1
                continue
            existing.add(h)
            tc = TestCase(problem_id=ctx.problem.id, test_type="generated", input_data=inp,
                          is_valid=True, validation_status="valid", validation_feedback="Accepted by validator",
                          generator_cmd=cmd[:255], input_bytes=len(inp.encode()),
                          generation_meta={"seed": sd, "gen_type": gtype, "args": args,
                                           "generator_artifact_id": str(gen_art.id), "generator_version": gen_art.version,
                                           "validator_artifact_id": str(val_art.id), "run_id": str(ctx.run.id),
                                           "validated_by_sha": ctx.report["compilations"]["val"]["source_sha256"]})
            ctx.db.add(tc)
            ctx.db.flush()
            saved.append({"seed": sd, "test_case_id": str(tc.id), "bytes": tc.input_bytes})
        ctx.progress(iterations_done=min(count, start + BATCH), iterations_total=count, current_seed=seeds[-1])

    ctx.report["generator"] = {"saved": saved, "invalid": invalid, "failures": failures, "oversized": oversized,
                               "duplicates": dupes,
                               "requested": count, "gen_type": gtype, "seed": seed0, "extra_args": args}
    summary = (f"{len(saved)} valid tests saved, {len(invalid)} rejected by validator, {len(failures)} generator failures, "
               f"{dupes} duplicates" + (f", {len(oversized)} skipped as too large to store" if oversized else ""))
    # Duplicates and oversized outputs are not failures; producing nothing usable at all is.
    return ("failed" if invalid or failures or not (saved or dupes) else "passed"), summary


# ─────────────────────────────────────────────────────────────────────────────
# Reference solution on stored tests
def _usable_tests(ctx: RunContext) -> List[TestCase]:
    return (ctx.db.query(TestCase)
            .filter(TestCase.problem_id == ctx.problem.id, TestCase.test_type != "invalid",
                    TestCase.validation_status.in_(("valid", "unchecked")))
            .order_by(TestCase.created_at).all())


def run_solution_on_tests(ctx: RunContext, exe: Executable, tests: List[TestCase], checker: Optional[Executable],
                          oracle: Dict[str, str], role: str = "sol") -> List[dict]:
    b = Bundle().add(role, exe)
    if checker:
        b.add("checker", checker)
    rows = []
    for start in range(0, len(tests), BATCH):
        if not ctx.time_left():
            ctx.log("Time budget exhausted")
            break
        chunk = tests[start:start + BATCH]
        steps = []
        for i, tc in enumerate(chunk):
            steps.append(ctx.sol_step(f"r{i}", b.cmd(role), stdin=tc.input_data.encode()))
            exp = oracle.get(str(tc.id))
            if checker and exp is not None:
                steps.append(ctx.aux_step(f"c{i}", b.cmd("checker", "input.txt", "output.txt", "answer.txt"),
                                          write={"input.txt": tc.input_data.encode(), "output.txt": {"from": f"r{i}"},
                                                 "answer.txt": exp.encode()}, requires=[f"r{i}"]))
        res = {r.id: r for r in ctx.sandbox.execute(b.files, steps, b.exec)}
        for i, tc in enumerate(chunk):
            exp = oracle.get(str(tc.id))
            r = classify(res[f"r{i}"], ctx.tl, ctx.mem)
            r = ctx.judge(r, exp, res.get(f"c{i}") if checker and exp is not None else None)
            rows.append({"test_case_id": str(tc.id), "test_type": tc.test_type, "has_expected": exp is not None,
                         "validation_status": tc.validation_status, **r.to_dict(preview=2048),
                         "_full_stdout": r.stdout})
        ctx.progress(iterations_done=min(len(tests), start + BATCH), iterations_total=len(tests))
    return rows


def _strip_private(rows):
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def run_reference(ctx: RunContext) -> Tuple[str, str]:
    ref = ctx.compile_spec("reference", ctx.cfg["reference"])
    chk = ctx.checker()
    tests = _usable_tests(ctx)
    if not tests:
        raise JobFailure("No valid or unchecked test cases to run. Import samples or generate tests first.")
    oracle = {str(t.id): t.expected_output for t in tests if t.expected_output is not None}
    rows = run_solution_on_tests(ctx, ref, tests, chk, oracle, "ref")
    saved = 0
    if ctx.cfg.get("save_outputs"):
        by_id = {str(t.id): t for t in tests}
        for r in rows:
            t = by_id[r["test_case_id"]]
            if t.expected_output is None and r["status"] == R.EXECUTED:
                t.expected_output = r["_full_stdout"]
                t.generation_meta = {**(t.generation_meta or {}), "expected_source": "reference_solution",
                                     "expected_run_id": str(ctx.run.id)}
                saved += 1
    rows = _strip_private(rows)
    bad = [r for r in rows if r["status"] not in (R.ACCEPTED, R.EXECUTED)]
    ctx.report["reference"] = {"results": rows, "checker": "testlib checker" if chk else "token comparison",
                               "judged": sum(1 for r in rows if r["has_expected"]),
                               "unjudged": sum(1 for r in rows if not r["has_expected"]),
                               "unchecked_inputs": sum(1 for t in tests if t.validation_status == "unchecked"),
                               "expected_outputs_saved": saved,
                               "note": "Unjudged tests have no expected answer; 'Executed' means the run finished "
                                       "cleanly, not that the output is correct."}
    if bad:
        f = bad[0]
        return "failed", f"Reference failed on {len(bad)}/{len(rows)} tests (first: test {f['test_case_id'][:8]} → {f['status']}: {f.get('error_details') or ''})"
    if len(rows) < len(tests):
        return "failed", f"Time budget exhausted after {len(rows)}/{len(tests)} tests"
    return "passed", f"Reference ran cleanly on {len(rows)} tests ({ctx.report['reference']['judged']} judged against expected answers)"


# ─────────────────────────────────────────────────────────────────────────────
# Differential / stress testing
def _save_cx(ctx, kind, inp, ref_out, cand_out, seed, details) -> Counterexample:
    cx = Counterexample(problem_id=ctx.problem.id, verification_run_id=ctx.run.id, kind=kind,
                        input_data=inp, ref_output=ref_out[:ctx.settings.MAX_INPUT_BYTES],
                        candidate_output=cand_out[:ctx.settings.MAX_INPUT_BYTES], seed=seed, details=details)
    ctx.db.add(cx)
    ctx.db.flush()
    return cx


def run_comparison(ctx: RunContext) -> Tuple[str, str]:
    differential = ctx.run.test_type == "differential"
    cand_name = "brute-force" if differential else "candidate"
    ref = ctx.compile_spec("reference", ctx.cfg["reference"])
    cand = ctx.compile_spec("candidate", ctx.cfg["candidate"])
    gen = ctx.compile_artifact("gen", "generator")
    val = ctx.compile_artifact("val", "validator")
    chk = ctx.checker()
    b = Bundle().add("gen", gen).add("val", val).add("ref", ref).add("cand", cand)
    if chk:
        b.add("checker", chk)
    cfg = ctx.cfg
    iters, seed0, gtype, args = cfg["iterations"], cfg["seed"], cfg["gen_type"], cfg["extra_args"]
    done, cxs, stop_reason, failure_kinds = 0, [], None, {}
    max_cx = 1 if cfg.get("stop_on_first", True) else 10

    for start in range(0, iters, BATCH):
        if not ctx.time_left():
            stop_reason = "time budget exhausted"
            break
        seeds = [seed0 + i for i in range(start, min(iters, start + BATCH))]
        steps = []
        for sd in seeds:
            steps += [
                ctx.aux_step(f"g{sd}", _gen_cmd(b, gtype, sd, args)),
                ctx.aux_step(f"v{sd}", b.cmd("val"), stdin={"from": f"g{sd}"}, requires=[f"g{sd}"]),
                ctx.sol_step(f"r{sd}", b.cmd("ref"), stdin={"from": f"g{sd}"}, requires=[f"v{sd}"]),
                ctx.sol_step(f"c{sd}", b.cmd("cand"), stdin={"from": f"g{sd}"}, requires=[f"v{sd}"]),
            ]
            if chk:
                steps.append(ctx.aux_step(f"k{sd}", b.cmd("checker", "input.txt", "output.txt", "answer.txt"),
                                          write={"input.txt": {"from": f"g{sd}"}, "output.txt": {"from": f"c{sd}"},
                                                 "answer.txt": {"from": f"r{sd}"}}, requires=[f"r{sd}", f"c{sd}"]))
        res = {r.id: r for r in ctx.sandbox.execute(b.files, steps, b.exec)}
        for sd in seeds:
            done += 1
            g, v = res[f"g{sd}"], res[f"v{sd}"]
            inp = _decode(g.stdout)
            if not g.clean_exit:
                failure_kinds["generator_failure"] = sd
                stop_reason = f"generator failed on seed {sd}: {classify(g, 10.0, 512).error_details}"
                break
            if not v.clean_exit:
                failure_kinds["validator_failure"] = sd
                ctx.report.setdefault("rejected_inputs", []).append(
                    {"seed": sd, "input_preview": inp[:500], "diagnostics": _decode(v.stderr)[:500]})
                stop_reason = (f"validator rejected generated input for seed {sd} — the generator or the "
                               f"validator is wrong; inspect the input")
                break
            rr = classify(res[f"r{sd}"], ctx.tl, ctx.mem)
            cr = classify(res[f"c{sd}"], ctx.tl, ctx.mem)
            meta = {"seed": sd, "gen_cmd": " ".join(["gen", gtype, str(sd), *args]),
                    "reference": rr.to_dict(preview=1024), "candidate": cr.to_dict(preview=1024)}
            if rr.status != R.EXECUTED:
                failure_kinds["reference_failure"] = sd
                cxs.append(_save_cx(ctx, "reference_failure", inp, rr.stdout, cr.stdout, sd,
                                    {**meta, "message": f"Reference solution: {rr.status} — {rr.error_details}"}))
            elif cr.status != R.EXECUTED:
                kind = "brute_failure" if differential else "candidate_failure"
                failure_kinds[kind] = sd
                cxs.append(_save_cx(ctx, kind, inp, rr.stdout, cr.stdout, sd,
                                    {**meta, "message": f"{cand_name}: {cr.status} — {cr.error_details}"}))
            else:
                cr = ctx.judge(cr, rr.stdout, res.get(f"k{sd}") if chk else None)
                if cr.status == R.INTERNAL_ERROR:
                    failure_kinds["checker_failure"] = sd
                    stop_reason = f"checker failed on seed {sd}: {cr.error_details}"
                    break
                if cr.status == R.WRONG_ANSWER:
                    failure_kinds["output_mismatch"] = sd
                    cxs.append(_save_cx(ctx, "mismatch", inp, rr.stdout, cr.stdout, sd,
                                        {**meta, "message": cr.error_details, "comparison": cr.comparison}))
            if len(cxs) >= max_cx:
                stop_reason = "counterexample found" if max_cx == 1 else f"{max_cx} counterexamples found"
                break
        ctx.progress(iterations_done=done, iterations_total=iters, current_seed=seed0 + done - 1,
                     counterexamples=len(cxs))
        if stop_reason:
            break

    if cxs and cfg.get("minimize", True):
        first = next((c for c in cxs if c.kind == "mismatch"), None)
        if first is not None:
            ctx.log(f"Minimizing counterexample {str(first.id)[:8]}")
            res_min = minimize(ctx, b, first.input_data, chk is not None)
            first.details = {**(first.details or {}), "minimization": res_min["report"]}
            if res_min["input"] is not None:
                first.minimized_input = res_min["input"]
                ctx.log(f"Minimized input from {len(first.input_data)} to {len(res_min['input'])} bytes")

    ctx.report["comparison"] = {
        "mode": ctx.run.test_type, "candidate_label": cand_name, "iterations_requested": iters,
        "iterations_completed": done, "seed": seed0, "gen_type": gtype, "extra_args": args,
        "stop_reason": stop_reason, "failure_kinds": failure_kinds,
        "counterexample_ids": [str(c.id) for c in cxs],
        "checker": "testlib checker" if chk else "token comparison",
        "note": ("Neither solution is assumed correct: a disagreement means at least one of them is wrong."
                 if differential else "Reference output is used as the oracle; it is a candidate oracle, not a proof."),
    }
    if failure_kinds:
        what = ", ".join(f"{k.replace('_', ' ')} (seed {v})" for k, v in failure_kinds.items())
        return "failed", f"After {done} iterations: {what}"
    if done < iters:
        return "failed", f"Stopped after {done}/{iters} iterations: {stop_reason}"
    return "passed", f"{done} iterations: reference and {cand_name} agreed on every generated input"


# ─────────────────────────────────────────────────────────────────────────────
# Candidate (WA / TLE / regression) testing
VERDICT_CODE = {R.ACCEPTED: "AC", R.WRONG_ANSWER: "WA", R.TLE: "TLE", R.MLE: "MLE", R.RUNTIME_ERROR: "RE",
                R.OUTPUT_LIMIT: "OLE"}


def _cpu_bound_tle(r: dict) -> bool:
    return r["status"] == R.TLE and r["time_ms"] >= r["time_limit_ms"] * 0.5


def run_candidate(ctx: RunContext) -> Tuple[str, str]:
    cand = ctx.compile_spec("candidate", ctx.cfg["candidate"])
    chk = ctx.checker()
    tests = _usable_tests(ctx)
    cx = None
    if ctx.cfg.get("counterexample_id"):
        cx = ctx.db.query(Counterexample).filter_by(id=uuid.UUID(ctx.cfg["counterexample_id"]),
                                                    problem_id=ctx.problem.id).first()
        if cx:  # transient test case object, not persisted
            tests = [TestCase(id=cx.id, problem_id=ctx.problem.id, test_type="counterexample",
                              input_data=cx.minimized_input or cx.input_data, validation_status="valid")] + tests
    if not tests:
        raise JobFailure("No test cases available. Import samples or generate tests first.")

    oracle = {str(t.id): t.expected_output for t in tests if t.expected_output is not None}
    missing = [t for t in tests if str(t.id) not in oracle]
    if missing:
        ref = ctx.compile_spec("reference", ctx.cfg["reference"])
        ctx.log(f"Computing oracle answers with the reference solution for {len(missing)} tests")
        for row in run_solution_on_tests(ctx, ref, missing, None, {}, "ref"):
            if row["status"] == R.EXECUTED:
                oracle[row["test_case_id"]] = row["_full_stdout"]
    unjudgeable = [str(t.id) for t in tests if str(t.id) not in oracle]

    rows = run_solution_on_tests(ctx, cand, [t for t in tests if str(t.id) in oracle], chk, oracle, "cand")

    # Re-run TLE tests to avoid trusting a single timing measurement.
    confirm = int(ctx.cfg.get("tle_confirm_runs", 2))
    by_id = {str(t.id): t for t in tests}
    for row in rows:
        if row["status"] == R.TLE and confirm > 0:
            again = run_solution_on_tests(ctx, cand, [by_id[row["test_case_id"]]] * confirm, None, {}, "cand")
            row["tle_reruns"] = [{"status": a["status"], "time_ms": a["time_ms"], "wall_ms": a["wall_ms"],
                                  "time_limit_ms": a["time_limit_ms"]} for a in again]
            # Confirmed only if every measurement is a CPU-bound timeout (not an idle/overloaded wall timeout).
            row["tle_confirmed"] = all(_cpu_bound_tle(a) for a in [row, *again])

    verdict, evidence = "AC", None
    for code_status in (R.WRONG_ANSWER, R.TLE, R.MLE, R.RUNTIME_ERROR, R.OUTPUT_LIMIT, R.INTERNAL_ERROR):
        hit = next((r for r in rows if r["status"] == code_status), None)
        if hit:
            verdict, evidence = VERDICT_CODE.get(code_status, "IE"), hit
            break
    if verdict == "TLE" and evidence and not evidence.get("tle_confirmed", confirm == 0):
        verdict = "TLE?"  # unstable / unconfirmed timing
    if evidence and verdict not in ("IE",):
        tc = by_id[evidence["test_case_id"]]
        saved = _save_cx(ctx, "mismatch" if verdict == "WA" else "candidate_failure", tc.input_data,
                         oracle.get(evidence["test_case_id"], ""), evidence["_full_stdout"], None,
                         {"message": f"{evidence['status']}: {evidence.get('error_details') or ''}",
                          "test_case_id": evidence["test_case_id"],
                          "candidate": {k: v for k, v in evidence.items() if not k.startswith("_")}})
        evidence_cx = str(saved.id)
    else:
        evidence_cx = None

    rows = _strip_private(rows)
    expected = ctx.cfg.get("expected_verdict")
    ctx.report["candidate"] = {
        "verdict": verdict, "expected_verdict": expected, "results": rows, "unjudgeable_tests": unjudgeable,
        "evidence_counterexample_id": evidence_cx, "time_limit_ms": int(ctx.tl * 1000),
        "checker": "testlib checker" if chk else "token comparison",
        "note": "Timings are measured in this sandbox (1 CPU, Docker on this host) and are evidence from this "
                "environment only, not universal performance guarantees.",
    }
    if ctx.cfg.get("counterexample_id") and cx:
        ctx.report["candidate"]["counterexample_rerun"] = next(
            (r for r in rows if r["test_case_id"] == str(cx.id)), None)
    if verdict == "IE":
        raise SandboxInfraError(f"Internal error while judging: {evidence.get('error_details')}")
    desc = f"Candidate verdict {verdict} on {len(rows)} tests" + (
        f" (first failure: {evidence['status']})" if evidence else "")
    if unjudgeable:
        desc += f"; {len(unjudgeable)} tests had no oracle answer"
    if expected:
        ok = verdict == expected
        return ("passed" if ok else "failed"), desc + f" — expected {expected}: {'matches' if ok else 'does NOT match'}"
    return ("passed" if verdict == "AC" and not unjudgeable else "failed"), desc


# ─────────────────────────────────────────────────────────────────────────────
def run_compile(ctx: RunContext) -> Tuple[str, str]:
    src, lang, label = ctx.resolve(ctx.cfg["target"])
    ctx.compile("target", src, lang, label)
    c = ctx.report["compilations"]["target"]
    return "passed", f"Compiled {label} with {c['version']} in {c['duration_ms']} ms"


HANDLERS: Dict[str, Callable[[RunContext], Tuple[str, str]]] = {
    "compile": run_compile,
    "validator": run_validator,
    "generate": run_generate,
    "reference": run_reference,
    "differential": run_comparison,
    "stress": run_comparison,
    "candidate": run_candidate,
}


def execute_run(db: Session, run: VerificationRun, sandbox: Optional[DockerSandbox] = None) -> VerificationRun:
    """Execute a claimed run (status already 'running'). Always leaves a terminal status."""
    ctx = RunContext(db, run, sandbox)
    run.started_at = run.started_at or _now()
    ctx.log(f"Starting {run.test_type} verification")
    try:
        if not ctx.problem:
            raise JobFailure("Problem no longer exists")
        handler = HANDLERS.get(run.test_type)
        if handler is None:
            raise JobFailure(f"Unsupported verification type {run.test_type}")
        status, summary = handler(ctx)
        run.status, run.summary = status, summary
    except Cancelled:
        # progress() commits before checking the flag, so all evidence so far is persisted.
        run.status, run.summary = "cancelled", "Cancelled by user"
        ctx.report["failure_kind"] = "cancelled"
    except JobFailure as jf:
        run.status, run.summary = "failed", jf.summary
        ctx.report.update(jf.report)
        ctx.report["failure_kind"] = ctx.report.get("failure_kind", "artifact")
    except SandboxUnavailable as exc:
        attempts = int((run.progress or {}).get("infra_attempts", 0))
        nothing_ran = not any(c.get("status") == "success" for c in ctx.report["compilations"].values())
        if nothing_ran and attempts < ctx.settings.INFRA_RETRY_LIMIT:
            # Safe retry: no sandbox execution happened, so re-queuing cannot duplicate side effects.
            run.status, run.started_at, run.worker_id = "queued", None, None
            run.progress = {**(run.progress or {}), "infra_attempts": attempts + 1}
            run.summary = f"Sandbox unavailable — re-queued (retry {attempts + 1}/{ctx.settings.INFRA_RETRY_LIMIT})"
            ctx.log(run.summary)

            db.commit()
            return run
        run.status, run.summary, run.error_message = "failed", "Sandbox unavailable — nothing was executed", str(exc)
        ctx.report["failure_kind"] = "infrastructure"
    except SandboxInfraError as exc:
        run.status, run.summary, run.error_message = "failed", "Execution infrastructure error", str(exc)
        ctx.report["failure_kind"] = "infrastructure"
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Verification run %s crashed", run.id)
        db.rollback()
        run.status, run.summary, run.error_message = "failed", "Internal worker error", str(exc)[:2000]
        ctx.report["failure_kind"] = "infrastructure"
    ctx.log(f"Finished: {run.status} — {run.summary}")
    run.report = json.loads(json.dumps(ctx.report, default=str))
    run.completed_at = _now()
    db.commit()
    return run
