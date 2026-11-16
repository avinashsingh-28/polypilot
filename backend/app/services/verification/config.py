"""
Verification job configuration: validation and clamping to server-defined maxima.
Users can lower limits, never raise them above the server maximum.
"""
import re
from typing import Any, Dict, Optional

from app.core.config import Settings

TEST_TYPES = ("compile", "validator", "generate", "reference", "differential", "stress", "candidate")
GEN_TYPES = ("small", "large", "edge")
ARG_RE = re.compile(r"^[A-Za-z0-9_=.,:+\-]{1,32}$")
SEED_MAX = 2**31 - 1


class ConfigError(ValueError):
    pass


def _num(raw: Dict[str, Any], key: str, default, lo, hi, cast=float):
    v = raw.get(key, default)
    if v is None:
        v = default
    try:
        v = cast(v)
    except (TypeError, ValueError):
        raise ConfigError(f"'{key}' must be a number")
    return max(lo, min(hi, v))


def _source_spec(raw: Any, field: str, required: bool, s: Settings) -> Optional[dict]:
    if raw is None:
        if required:
            raise ConfigError(f"'{field}' is required (artifact_id, artifact_type, repair_id or source+language)")
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"'{field}' must be an object")
    out = {}
    for k in ("artifact_id", "repair_id", "artifact_type"):
        if raw.get(k):
            out[k] = str(raw[k])[:100]
    if raw.get("source") is not None:
        src = str(raw["source"])
        if len(src.encode()) > s.MAX_SOURCE_BYTES:
            raise ConfigError(f"'{field}.source' exceeds {s.MAX_SOURCE_BYTES} bytes")
        out["source"] = src
        out["language"] = str(raw.get("language") or "cpp")[:20]
        out["label"] = str(raw.get("label") or "inline source")[:80]
    if not out:
        raise ConfigError(f"'{field}' must reference an artifact, a repair, or inline source")
    return out


def _args(raw: Any):
    if raw in (None, ""):
        return []
    if isinstance(raw, str):
        raw = raw.split()
    if not isinstance(raw, list) or len(raw) > 8:
        raise ConfigError("'extra_args' must be a list of at most 8 arguments")
    for a in raw:
        if not isinstance(a, str) or not ARG_RE.match(a):
            raise ConfigError(f"Invalid generator argument {a!r} (allowed: letters, digits, _=.,:+-; max 32 chars)")
    return list(raw)


def effective_config(test_type: str, raw: Optional[dict], problem, s: Settings) -> dict:
    if test_type not in TEST_TYPES:
        raise ConfigError(f"Unknown verification type '{test_type}'. Allowed: {', '.join(TEST_TYPES)}")
    raw = dict(raw or {})
    p_tl = float(problem.time_limit_seconds or s.DEFAULT_TIME_LIMIT_SEC)
    p_mem = int(problem.memory_limit_mb or 256)
    cfg: Dict[str, Any] = {
        "time_limit_sec": _num(raw, "time_limit_sec", p_tl, 0.1, s.MAX_TIME_LIMIT_SEC),
        "memory_mb": _num(raw, "memory_mb", min(p_mem, s.MAX_MEMORY_MB), 16, s.MAX_MEMORY_MB, int),
        "output_limit_bytes": _num(raw, "output_limit_bytes", s.MAX_OUTPUT_BYTES, 1024, s.MAX_OUTPUT_BYTES, int),
        "max_seconds": _num(raw, "max_seconds", min(600, s.MAX_JOB_DURATION_SEC), 10, s.MAX_JOB_DURATION_SEC, int),
    }
    tol = raw.get("float_tolerance")
    cfg["float_tolerance"] = None if tol in (None, "") else _num(raw, "float_tolerance", 1e-6, 0.0, 1e-2)

    if test_type == "compile":
        cfg["target"] = _source_spec(raw.get("target"), "target", True, s)
    elif test_type == "validator":
        cfg["include_mutations"] = bool(raw.get("include_mutations", True))
    elif test_type in ("generate", "differential", "stress"):
        cfg["seed"] = _num(raw, "seed", 1, 0, SEED_MAX, int)
        cfg["gen_type"] = raw.get("gen_type") or ("large" if test_type == "generate" else "small")
        if cfg["gen_type"] not in GEN_TYPES:
            raise ConfigError(f"'gen_type' must be one of {GEN_TYPES}")
        cfg["extra_args"] = _args(raw.get("extra_args"))
        if test_type == "generate":
            cfg["count"] = _num(raw, "count", 10, 1, s.MAX_GENERATED_TESTS, int)
        else:
            cfg["iterations"] = _num(raw, "iterations", 100, 1, s.MAX_STRESS_ITERATIONS, int)
            cfg["stop_on_first"] = bool(raw.get("stop_on_first", True))
            cfg["minimize"] = bool(raw.get("minimize", True))
            cfg["reference"] = _source_spec(raw.get("reference") or {"artifact_type": "reference_solution"},
                                            "reference", True, s)
            default_cand = {"artifact_type": "brute_force"} if test_type == "differential" else None
            cfg["candidate"] = _source_spec(raw.get("candidate") or default_cand, "candidate", True, s)
    elif test_type == "reference":
        cfg["reference"] = _source_spec(raw.get("reference") or {"artifact_type": "reference_solution"},
                                        "reference", True, s)
        cfg["save_outputs"] = bool(raw.get("save_outputs", False))
    elif test_type == "candidate":
        cfg["candidate"] = _source_spec(raw.get("candidate"), "candidate", True, s)
        cfg["reference"] = _source_spec(raw.get("reference") or {"artifact_type": "reference_solution"},
                                        "reference", True, s)
        ev = raw.get("expected_verdict")
        if ev not in (None, "", "AC", "WA", "TLE", "RE", "MLE"):
            raise ConfigError("'expected_verdict' must be one of AC, WA, TLE, RE, MLE")
        cfg["expected_verdict"] = ev or None
        cfg["tle_confirm_runs"] = _num(raw, "tle_confirm_runs", 2, 0, 3, int)
        cfg["counterexample_id"] = str(raw["counterexample_id"]) if raw.get("counterexample_id") else None
    return cfg
