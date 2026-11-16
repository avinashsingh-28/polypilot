#!/usr/bin/env python3
"""
PolyPilot sandbox harness (trusted code, runs as PID 1 inside the container).

Protocol
--------
stdin  : one JSON request
    {
      "files": {"name": {"b64": "...", "exec": bool}},
      "steps": [
        {
          "id": "run",
          "cmd": ["./prog"],
          "stdin": {"b64": "..."} | {"from": "<step id>"} | null,
          "write": {"input.txt": {"from": "gen"} | {"b64": "..."}},
          "requires": ["<step id>", ...],     # skipped unless all exited 0 cleanly
          "time_limit": 2.0,                  # CPU seconds
          "wall_limit": 4.0,                  # wall-clock seconds
          "memory_mb": 256,
          "output_limit": 16777216,           # bytes (stdout and any written file)
          "collect": ["prog"]                 # workspace files returned as base64
        }
      ]
    }
stdout : one JSON response {"ok": true, "steps": [...], "env": {...}}

Untrusted programs never write to this process's stdout: their stdout/stderr
are redirected to files inside the tmpfs workspace. Because this harness is
PID 1 of the container's PID namespace, untrusted processes cannot kill it,
and after every step all remaining processes are SIGKILLed.
"""
import base64
import ctypes
import json
import math
import os
import re
import resource
import signal
import subprocess
import sys
import time

WORK = "/workspace"
MAX_REQUEST_BYTES = 64 * 1024 * 1024
MAX_COLLECT_BYTES = 32 * 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024
NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,63}$")
CHILD_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"}


def _fail(msg):
    sys.stdout.write(json.dumps({"ok": False, "error": msg}))
    sys.stdout.flush()
    sys.exit(0)


def _safe_name(name):
    if not isinstance(name, str) or not NAME_RE.match(name) or ".." in name:
        _fail(f"invalid file name: {name!r}")
    return os.path.join(WORK, name)


def _harden_self():
    # Prevent same-uid processes from ptracing / reading /proc/1/mem or fds.
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        PR_SET_DUMPABLE = 4
        return libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) == 0
    except Exception:
        return False


def _oom_kills():
    try:
        with open("/sys/fs/cgroup/memory.events") as f:
            for line in f:
                k, v = line.split()
                if k == "oom_kill":
                    return int(v)
    except Exception:
        pass
    return None


def _kill_strays():
    """SIGKILL every process in the namespace except ourselves, then reap."""
    try:
        os.kill(-1, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except Exception:
        pass
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            time.sleep(0.005)


def _read_capped(path, cap):
    try:
        with open(path, "rb") as f:
            return f.read(cap)
    except FileNotFoundError:
        return b""


def _run_step(idx, step, stdin_bytes):
    tl = max(0.05, float(step.get("time_limit", 2.0)))
    wall = max(tl, float(step.get("wall_limit", tl * 2 + 1)))
    mem_mb = int(step.get("memory_mb", 256))
    out_limit = int(step.get("output_limit", 16 * 1024 * 1024))
    cmd = step["cmd"]
    if not isinstance(cmd, list) or not cmd or not all(isinstance(c, str) for c in cmd):
        _fail("invalid cmd")

    in_path = os.path.join(WORK, f".pp_{idx}.in")
    out_path = os.path.join(WORK, f".pp_{idx}.out")
    err_path = os.path.join(WORK, f".pp_{idx}.err")
    with open(in_path, "wb") as f:
        f.write(stdin_bytes or b"")

    cpu_hard = int(math.ceil(tl)) + 1
    mem_bytes = mem_mb * 1024 * 1024

    def preexec():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_hard, cpu_hard))
        resource.setrlimit(resource.RLIMIT_FSIZE, (out_limit, out_limit))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_STACK, (mem_bytes, mem_bytes))
        try:
            with open("/proc/self/oom_score_adj", "w") as f:
                f.write("1000")
        except Exception:
            pass

    oom_before = _oom_kills()
    fin = open(in_path, "rb")
    fout = open(out_path, "wb")
    ferr = open(err_path, "wb")
    start = time.monotonic()
    wall_timed_out = False
    try:
        proc = subprocess.Popen(
            cmd, stdin=fin, stdout=fout, stderr=ferr, cwd=WORK, env=CHILD_ENV,
            preexec_fn=preexec, start_new_session=True, close_fds=True,
        )
    except (OSError, ValueError) as exc:
        fin.close(); fout.close(); ferr.close()
        return {"id": step.get("id"), "spawn_error": str(exc), "exit_code": None,
                "signal": None, "cpu_ms": 0, "wall_ms": 0, "peak_kb": 0,
                "timed_out": False, "wall_timed_out": False, "oom_killed": False,
                "output_exceeded": False, "stdout_b64": "", "stderr_b64": "",
                "stdout_bytes": 0}
    finally:
        pass

    status, ru = 0, None
    while True:
        pid, status, ru = os.wait4(proc.pid, os.WNOHANG)
        if pid == proc.pid:
            break
        if time.monotonic() - start > wall:
            wall_timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except Exception:
                pass
            _, status, ru = os.wait4(proc.pid, 0)
            break
        time.sleep(0.002)
    wall_ms = int((time.monotonic() - start) * 1000)
    proc.returncode = 0  # status already reaped; stop Popen from waiting again
    fin.close(); fout.close(); ferr.close()
    _kill_strays()

    exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else None
    sig = os.WTERMSIG(status) if os.WIFSIGNALED(status) else None
    cpu_s = (ru.ru_utime + ru.ru_stime) if ru else 0.0
    peak_kb = int(ru.ru_maxrss) if ru else 0
    oom_after = _oom_kills()
    oom_killed = (oom_before is not None and oom_after is not None and oom_after > oom_before)

    out_size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
    output_exceeded = sig == signal.SIGXFSZ or out_size >= out_limit
    stdout = _read_capped(out_path, out_limit)
    stderr = _read_capped(err_path, MAX_STDERR_BYTES)
    for p in (in_path, out_path, err_path):
        try:
            os.unlink(p)
        except Exception:
            pass

    return {
        "id": step.get("id"),
        "exit_code": exit_code,
        "signal": sig,
        "cpu_ms": int(cpu_s * 1000),
        "wall_ms": wall_ms,
        "peak_kb": peak_kb,
        "timed_out": wall_timed_out or cpu_s > tl or sig == signal.SIGXCPU,
        "wall_timed_out": wall_timed_out,
        "oom_killed": oom_killed,
        "memory_exceeded": oom_killed or peak_kb > mem_mb * 1024,
        "output_exceeded": output_exceeded,
        "stdout_b64": base64.b64encode(stdout).decode(),
        "stderr_b64": base64.b64encode(stderr).decode(),
        "stdout_bytes": out_size,
    }, stdout


def _clean_ok(res):
    return (res.get("exit_code") == 0 and not res.get("timed_out")
            and not res.get("memory_exceeded") and not res.get("output_exceeded"))


def main():
    hardened = _harden_self()
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        _fail("request too large")
    try:
        req = json.loads(raw)
    except Exception:
        _fail("malformed request")

    for name, spec in (req.get("files") or {}).items():
        path = _safe_name(name)
        with open(path, "wb") as f:
            f.write(base64.b64decode(spec.get("b64", "")))
        os.chmod(path, 0o700 if spec.get("exec") else 0o600)

    outputs, clean, results = {}, {}, []
    for idx, step in enumerate(req.get("steps") or []):
        sid = step.get("id") or f"s{idx}"
        if any(not clean.get(r, False) for r in step.get("requires") or []):
            results.append({"id": sid, "skipped": True})
            clean[sid] = False
            continue
        for name, src in (step.get("write") or {}).items():
            path = _safe_name(name)
            data = outputs.get(src["from"], b"") if "from" in src else base64.b64decode(src.get("b64", ""))
            with open(path, "wb") as f:
                f.write(data)
        stdin_spec = step.get("stdin")
        stdin_bytes = b""
        if stdin_spec:
            stdin_bytes = outputs.get(stdin_spec["from"], b"") if "from" in stdin_spec \
                else base64.b64decode(stdin_spec.get("b64", ""))
        ran = _run_step(idx, step, stdin_bytes)
        if isinstance(ran, dict):  # spawn error
            res, stdout = ran, b""
        else:
            res, stdout = ran
        res["id"] = sid
        outputs[sid] = stdout
        clean[sid] = _clean_ok(res)
        collected, budget = {}, MAX_COLLECT_BYTES
        for name in step.get("collect") or []:
            path = _safe_name(name)
            if clean[sid] and os.path.isfile(path) and os.path.getsize(path) <= budget:
                data = _read_capped(path, budget)
                budget -= len(data)
                collected[name] = base64.b64encode(data).decode()
        res["files"] = collected
        results.append(res)

    env = {"uid": os.getuid(), "gid": os.getgid(), "pid": os.getpid(), "dumpable_off": hardened}
    sys.stdout.write(json.dumps({"ok": True, "steps": results, "env": env}))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
