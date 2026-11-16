"""
Counterexample minimization (greedy, validator-gated).

A reduced input is accepted only if (1) the sandboxed validator accepts it and
(2) the reference and candidate still both run cleanly and still disagree.
Otherwise the original counterexample is kept.

Strategies are plain functions `input -> iterable of candidate inputs`, so
problem-specific reducers can be added to STRATEGIES later.
"""
import re
from typing import Callable, Iterable, List

from app.services.sandbox import classify, judge_tokens, apply_checker
from app.services.sandbox import runner as R

_INT = re.compile(r"^-?\d+$")
MAX_ROUNDS = 25
MAX_ATTEMPTS = 120
PER_CONTAINER = 8


def shrink_array(inp: str) -> Iterable[str]:
    """If the first token is n and a later line has n tokens (or n item lines follow), drop one element."""
    lines = inp.rstrip("\n").split("\n")
    head = lines[0].split() if lines else []
    if not head or not _INT.match(head[0]):
        return
    n = int(head[0])
    if n <= 1 or n > 10**6:
        return
    new_head = " ".join([str(n - 1)] + head[1:])
    for li in range(1, len(lines)):
        toks = lines[li].split()
        if len(toks) == n:
            for j in sorted({n - 1, 0, n // 2}):
                rest = toks[:j] + toks[j + 1:]
                yield "\n".join([new_head] + lines[1:li] + [" ".join(rest)] + lines[li + 1:]) + "\n"
            return
    if len(lines) - 1 == n:  # n item lines
        for j in sorted({n, 1, (n + 1) // 2}):
            yield "\n".join([new_head] + lines[1:j] + lines[j + 1:]) + "\n"


def shrink_numbers(inp: str) -> Iterable[str]:
    """Reduce magnitudes of integer tokens (0, 1, half), preserving layout."""
    parts = re.split(r"(\s+)", inp)
    for i, p in enumerate(parts):
        if not _INT.match(p):
            continue
        v = int(p)
        for c in (0, 1, v // 2, v - 1):
            if 0 <= abs(c) < abs(v):
                yield "".join(parts[:i] + [str(c)] + parts[i + 1:])


STRATEGIES: List[Callable[[str], Iterable[str]]] = [shrink_array, shrink_numbers]


def minimize(ctx, bundle, original: str, has_checker: bool) -> dict:
    current, tried, attempts, accepted_steps = original, {original}, 0, 0
    for _ in range(MAX_ROUNDS):
        if attempts >= MAX_ATTEMPTS or not ctx.time_left():
            break
        cands: List[str] = []
        for strat in STRATEGIES:
            for c in strat(current):
                if c not in tried and len(c) <= len(current):
                    cands.append(c)
                    tried.add(c)
                if len(cands) >= PER_CONTAINER:
                    break
            if len(cands) >= PER_CONTAINER:
                break
        if not cands:
            break
        ctx.progress(minimization_attempts=attempts)
        attempts += len(cands)
        steps = []
        for i, c in enumerate(cands):
            steps += [
                ctx.aux_step(f"v{i}", bundle.cmd("val"), stdin=c.encode()),
                ctx.sol_step(f"r{i}", bundle.cmd("ref"), stdin=c.encode(), requires=[f"v{i}"]),
                ctx.sol_step(f"c{i}", bundle.cmd("cand"), stdin=c.encode(), requires=[f"v{i}"]),
            ]
            if has_checker:
                steps.append(ctx.aux_step(f"k{i}", bundle.cmd("checker", "input.txt", "output.txt", "answer.txt"),
                                          write={"input.txt": c.encode(), "output.txt": {"from": f"c{i}"},
                                                 "answer.txt": {"from": f"r{i}"}}, requires=[f"r{i}", f"c{i}"]))
        res = {r.id: r for r in ctx.sandbox.execute(bundle.files, steps, bundle.exec)}
        progressed = False
        for i, c in enumerate(cands):
            if not res[f"v{i}"].clean_exit:
                continue
            rr = classify(res[f"r{i}"], ctx.tl, ctx.mem)
            cr = classify(res[f"c{i}"], ctx.tl, ctx.mem)
            if rr.status != R.EXECUTED or cr.status != R.EXECUTED:
                continue
            cr = apply_checker(cr, res.get(f"k{i}")) if has_checker else \
                judge_tokens(cr, rr.stdout, ctx.cfg.get("float_tolerance"))
            if cr.status == R.WRONG_ANSWER:
                current, progressed = c, True
                accepted_steps += 1
                break
        if not progressed:
            break
    changed = current != original
    return {"input": current if changed else None,
            "report": {"attempts": attempts, "reductions": accepted_steps, "changed": changed,
                       "original_bytes": len(original), "minimized_bytes": len(current),
                       "rule": "validator-accepted and mismatch reproduced"}}
