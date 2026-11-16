"""
Execution + judging helpers.

Raw execution never yields "Accepted": a program that exits cleanly is
"Executed" until its output is judged against an expected answer (token
comparison) or by a testlib checker.
"""
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from app.services.sandbox.comparator import TokenComparator
from app.services.sandbox.compiler import Executable
from app.services.sandbox.driver import DockerSandbox, Step, StepResult, get_sandbox

ACCEPTED = "Accepted"
WRONG_ANSWER = "Wrong Answer"
TLE = "Time Limit Exceeded"
MLE = "Memory Limit Exceeded"
RUNTIME_ERROR = "Runtime Error"
OUTPUT_LIMIT = "Output Limit Exceeded"
COMPILATION_ERROR = "Compilation Error"
INTERNAL_ERROR = "Internal Error"
EXECUTED = "Executed"          # ran cleanly, output not judged
SKIPPED = "Skipped"

SIGNAL_NAMES = {4: "SIGILL", 6: "SIGABRT", 7: "SIGBUS", 8: "SIGFPE", 9: "SIGKILL", 11: "SIGSEGV",
                24: "SIGXCPU", 25: "SIGXFSZ"}
PREVIEW = 4096


@dataclass
class ExecutionResult:
    status: str
    stdout: str
    stderr: str
    exit_code: Optional[int]
    signal: Optional[int]
    time_ms: int                  # CPU time (user+sys)
    wall_ms: int
    peak_memory_kb: int           # ru_maxrss of the process
    time_limit_ms: int
    memory_limit_mb: int
    timed_out: bool = False
    wall_timed_out: bool = False
    memory_exceeded: bool = False
    output_exceeded: bool = False
    error_details: Optional[str] = None
    comparison: Optional[dict] = None

    def to_dict(self, preview: int = PREVIEW) -> dict:
        d = asdict(self)
        d["stdout"] = self.stdout[:preview]
        d["stdout_truncated"] = len(self.stdout) > preview
        d["stderr"] = self.stderr[:preview]
        return d


def classify(res: StepResult, time_limit: float, memory_mb: int) -> ExecutionResult:
    out = res.stdout.decode("utf-8", "replace")
    err = res.stderr.decode("utf-8", "replace")
    base = dict(stdout=out, stderr=err, exit_code=res.exit_code, signal=res.signal,
                time_ms=res.cpu_ms, wall_ms=res.wall_ms, peak_memory_kb=res.peak_kb,
                time_limit_ms=int(time_limit * 1000), memory_limit_mb=memory_mb,
                timed_out=res.timed_out, wall_timed_out=res.wall_timed_out,
                memory_exceeded=res.memory_exceeded, output_exceeded=res.output_exceeded)
    if res.skipped:
        return ExecutionResult(SKIPPED, **{**base, "stdout": "", "stderr": ""},
                               error_details="Skipped because a prerequisite step failed")
    if res.spawn_error:
        return ExecutionResult(INTERNAL_ERROR, **base, error_details=f"Failed to start: {res.spawn_error}")
    if res.memory_exceeded:
        return ExecutionResult(MLE, **base, error_details=(
            f"Peak memory {res.peak_kb // 1024} MB exceeded limit {memory_mb} MB"
            + (" (killed by cgroup OOM killer)" if res.oom_killed else "")))
    if res.timed_out:
        if res.wall_timed_out and res.cpu_ms < time_limit * 1000 * 0.5:
            detail = (f"Wall-clock limit reached with only {res.cpu_ms} ms CPU used: the program was "
                      f"blocked/idle or the host was overloaded (inconclusive as a performance result)")
        else:
            detail = f"CPU time {res.cpu_ms} ms exceeded limit {int(time_limit * 1000)} ms"
        return ExecutionResult(TLE, **base, error_details=detail)
    if res.output_exceeded:
        return ExecutionResult(OUTPUT_LIMIT, **base, error_details="Program output exceeded the output limit")
    if res.signal is not None:
        return ExecutionResult(RUNTIME_ERROR, **base,
                               error_details=f"Killed by signal {SIGNAL_NAMES.get(res.signal, res.signal)}")
    if res.exit_code != 0:
        return ExecutionResult(RUNTIME_ERROR, **base, error_details=f"Exited with code {res.exit_code}")
    return ExecutionResult(EXECUTED, **base)


def judge_tokens(result: ExecutionResult, expected: str,
                 float_tolerance: Optional[float] = None) -> ExecutionResult:
    """Apply token comparison to an EXECUTED result."""
    if result.status != EXECUTED:
        return result
    cmp = TokenComparator(float_tolerance).compare(result.stdout, expected)
    result.comparison = cmp.to_dict()
    result.status = ACCEPTED if cmp.matched else WRONG_ANSWER
    if not cmp.matched:
        result.error_details = cmp.message
    return result


def apply_checker(result: ExecutionResult, chk: Optional[StepResult]) -> ExecutionResult:
    """Apply a testlib checker verdict (exit 0 OK, 1 WA, 2 PE, other = checker failure)."""
    if result.status != EXECUTED:
        return result
    if chk is None or chk.skipped:
        result.status = INTERNAL_ERROR
        result.error_details = "Checker did not run"
        return result
    msg = (chk.stderr or chk.stdout).decode("utf-8", "replace").strip()[:1000]
    result.comparison = {"checker_exit_code": chk.exit_code, "checker_message": msg,
                         "matched": chk.exit_code == 0}
    if chk.exit_code == 0 and not chk.timed_out:
        result.status = ACCEPTED
    elif chk.exit_code in (1, 2) and not chk.timed_out:
        result.status = WRONG_ANSWER
        result.error_details = f"Checker: {msg}" if msg else "Checker rejected the output"
    else:
        result.status = INTERNAL_ERROR
        result.error_details = f"Checker failed (exit {chk.exit_code}{', timeout' if chk.timed_out else ''}): {msg}"
    return result


class Bundle:
    """Collects executables (by role) into one container request."""

    def __init__(self):
        self.files: Dict[str, bytes] = {}
        self.cmds: Dict[str, List[str]] = {}
        self.exec: List[str] = []

    def add(self, role: str, exe: Executable) -> "Bundle":
        files, cmd, ex = exe.materialize(role)
        self.files.update(files)
        self.cmds[role] = cmd
        self.exec.extend(ex)
        return self

    def cmd(self, role: str, *args: str) -> List[str]:
        return self.cmds[role] + list(args)


def run_program(exe: Executable, input_data: str, time_limit: float, memory_mb: int,
                output_limit: int, expected: Optional[str] = None,
                sandbox: Optional[DockerSandbox] = None) -> ExecutionResult:
    """Run one program once; judge by tokens only if an expected answer is given."""
    sb = sandbox or get_sandbox()
    b = Bundle().add("prog", exe)
    (res,) = sb.execute(b.files, [Step("run", b.cmd("prog"), time_limit=time_limit, memory_mb=memory_mb,
                                       output_limit=output_limit, stdin=input_data.encode())], b.exec)
    r = classify(res, time_limit, memory_mb)
    return judge_tokens(r, expected) if expected is not None else r
