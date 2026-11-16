"""
Secure Docker sandbox driver for PolyPilot.

This module NEVER executes untrusted code on the host. It only launches a
locked-down Docker container whose entrypoint is the trusted harness
(backend/sandbox/harness.py). All files are sent through stdin as JSON, so
no host directory is ever bind-mounted into the container.

Container restrictions (every run):
  --network none, --read-only root filesystem, tmpfs /workspace and /tmp,
  --cap-drop ALL, --security-opt no-new-privileges, Docker default seccomp
  profile (never disabled), --pids-limit, --memory == --memory-swap (no swap),
  --cpus, --ulimit nofile, --ipc none, non-root user 10001, no environment
  variables from the host, no devices, no Docker socket, --rm + forced
  removal on host-side timeout.

Inside the container the harness applies per-step rlimits (CPU, file size,
core, stack), a wall-clock timeout, and kills all stray processes between
steps.
"""
import base64
import json
import logging
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SANDBOX_LABEL = "polypilot.sandbox=1"


class SandboxUnavailable(RuntimeError):
    """Docker (or the sandbox image) is not available. Nothing was executed."""


class SandboxInfraError(RuntimeError):
    """The sandbox infrastructure failed (not the user's program)."""


@dataclass
class Step:
    id: str
    cmd: List[str]
    time_limit: float
    memory_mb: int
    output_limit: int
    wall_limit: Optional[float] = None
    stdin: Optional[Union[bytes, Dict[str, str]]] = None   # bytes literal or {"from": step_id}
    write: Dict[str, Union[bytes, Dict[str, str]]] = field(default_factory=dict)
    requires: List[str] = field(default_factory=list)
    collect: List[str] = field(default_factory=list)

    def effective_wall(self) -> float:
        return self.wall_limit if self.wall_limit is not None else self.time_limit * 2 + 1.0

    def to_json(self) -> dict:
        def src(v):
            if isinstance(v, (bytes, bytearray)):
                return {"b64": base64.b64encode(bytes(v)).decode()}
            return {"from": v["from"]}

        return {
            "id": self.id,
            "cmd": self.cmd,
            "stdin": src(self.stdin) if self.stdin is not None else None,
            "write": {k: src(v) for k, v in self.write.items()},
            "requires": self.requires,
            "time_limit": self.time_limit,
            "wall_limit": self.effective_wall(),
            "memory_mb": self.memory_mb,
            "output_limit": self.output_limit,
            "collect": self.collect,
        }


@dataclass
class StepResult:
    id: str
    skipped: bool = False
    spawn_error: Optional[str] = None
    exit_code: Optional[int] = None
    signal: Optional[int] = None
    cpu_ms: int = 0
    wall_ms: int = 0
    peak_kb: int = 0
    timed_out: bool = False
    wall_timed_out: bool = False
    oom_killed: bool = False
    memory_exceeded: bool = False
    output_exceeded: bool = False
    stdout: bytes = b""
    stderr: bytes = b""
    stdout_bytes: int = 0
    files: Dict[str, bytes] = field(default_factory=dict)

    @property
    def clean_exit(self) -> bool:
        return (not self.skipped and self.spawn_error is None and self.exit_code == 0
                and not self.timed_out and not self.memory_exceeded and not self.output_exceeded)

    @classmethod
    def from_json(cls, d: dict) -> "StepResult":
        if d.get("skipped"):
            return cls(id=d["id"], skipped=True)
        return cls(
            id=d["id"],
            spawn_error=d.get("spawn_error"),
            exit_code=d.get("exit_code"),
            signal=d.get("signal"),
            cpu_ms=int(d.get("cpu_ms") or 0),
            wall_ms=int(d.get("wall_ms") or 0),
            peak_kb=int(d.get("peak_kb") or 0),
            timed_out=bool(d.get("timed_out")),
            wall_timed_out=bool(d.get("wall_timed_out")),
            oom_killed=bool(d.get("oom_killed")),
            memory_exceeded=bool(d.get("memory_exceeded")),
            output_exceeded=bool(d.get("output_exceeded")),
            stdout=base64.b64decode(d.get("stdout_b64") or ""),
            stderr=base64.b64decode(d.get("stderr_b64") or ""),
            stdout_bytes=int(d.get("stdout_bytes") or 0),
            files={k: base64.b64decode(v) for k, v in (d.get("files") or {}).items()},
        )


class DockerSandbox:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.image = self.settings.SANDBOX_IMAGE
        self._mode: Optional[str] = None
        self._sem = threading.BoundedSemaphore(max(1, self.settings.SANDBOX_MAX_CONCURRENT))

    # ── Docker access ────────────────────────────────────────────────────────
    def _prefix(self) -> List[str]:
        mode = self.mode()
        if mode == "wsl":
            return ["wsl", "-d", self.settings.SANDBOX_WSL_DISTRO, "-e", "docker"]
        if mode == "native":
            return ["docker"]
        raise SandboxUnavailable(
            "Docker is not available. Install Docker (see README 'Phase 4 sandbox setup') "
            "and build the image: docker build -t polypilot-sandbox:latest backend/sandbox"
        )

    def mode(self) -> str:
        if self._mode is not None:
            return self._mode
        wanted = self.settings.SANDBOX_DOCKER_MODE.lower()
        candidates = []
        if wanted in ("auto", "native"):
            candidates.append(("native", ["docker"]))
        if wanted in ("auto", "wsl") and shutil.which("wsl"):
            candidates.append(("wsl", ["wsl", "-d", self.settings.SANDBOX_WSL_DISTRO, "-e", "docker"]))
        self._mode = "unavailable"
        for name, prefix in candidates:
            try:
                r = subprocess.run(prefix + ["version", "--format", "{{.Server.Version}}"],
                                   capture_output=True, timeout=15)
                if r.returncode == 0 and r.stdout.strip():
                    self._mode = name
                    break
            except (OSError, subprocess.SubprocessError):
                continue
        return self._mode

    def status(self) -> dict:
        info = {"mode": self.mode(), "image": self.image, "available": False,
                "server_version": None, "image_present": False}
        if info["mode"] == "unavailable":
            return info
        try:
            r = subprocess.run(self._prefix() + ["version", "--format", "{{.Server.Version}}"],
                               capture_output=True, timeout=15)
            info["server_version"] = r.stdout.decode().strip() or None
            r = subprocess.run(self._prefix() + ["image", "inspect", self.image, "--format", "{{.Id}}"],
                               capture_output=True, timeout=15)
            info["image_present"] = r.returncode == 0
            info["available"] = info["image_present"] and bool(info["server_version"])
        except (OSError, subprocess.SubprocessError) as exc:
            info["error"] = str(exc)
        return info

    def cleanup_orphans(self) -> int:
        """Remove any leftover sandbox containers (e.g. after a worker crash)."""
        try:
            r = subprocess.run(self._prefix() + ["ps", "-aq", "--filter", f"label={SANDBOX_LABEL}"],
                               capture_output=True, timeout=30)
            ids = r.stdout.decode().split()
            if ids:
                subprocess.run(self._prefix() + ["rm", "-f"] + ids, capture_output=True, timeout=60)
            return len(ids)
        except (OSError, subprocess.SubprocessError, SandboxUnavailable):
            return 0

    def _force_remove(self, name: str) -> None:
        try:
            subprocess.run(self._prefix() + ["rm", "-f", name], capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            logger.error("Failed to remove sandbox container %s", name)

    # ── Execution ────────────────────────────────────────────────────────────
    def docker_args(self, name: str, memory_mb: int, cpus: float, pids: int) -> List[str]:
        s = self.settings
        return [
            "run", "--rm", "-i",
            "--name", name,
            "--label", SANDBOX_LABEL,
            "--network", "none",
            "--read-only",
            "--tmpfs", f"/workspace:rw,exec,nosuid,nodev,size={s.SANDBOX_WORKSPACE_MB}m,mode=0700,uid=10001,gid=10001",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
            "--memory", f"{memory_mb}m",
            "--memory-swap", f"{memory_mb}m",
            "--cpus", str(cpus),
            "--pids-limit", str(pids),
            "--ulimit", "nofile=256:256",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--ipc", "none",
            "--log-driver", "none",
            "--user", "10001:10001",
            "--hostname", "sandbox",
            "--workdir", "/workspace",
            *(["--runtime", s.SANDBOX_RUNTIME] if s.SANDBOX_RUNTIME else []),
            self.image,
        ]

    def execute(self, files: Dict[str, bytes], steps: List[Step],
                executable: Optional[List[str]] = None) -> List[StepResult]:
        """Run the given steps in one fresh container. Raises SandboxUnavailable / SandboxInfraError."""
        prefix = self._prefix()
        executable = set(executable or [])
        payload = json.dumps({
            "files": {k: {"b64": base64.b64encode(v).decode(), "exec": k in executable}
                      for k, v in files.items()},
            "steps": [st.to_json() for st in steps],
        }).encode()

        # tmpfs pages and the harness itself are charged to the memory cgroup.
        mem = max(st.memory_mb for st in steps) + self.settings.SANDBOX_MEMORY_OVERHEAD_MB
        total_wall = sum(st.effective_wall() for st in steps)
        host_timeout = total_wall + self.settings.SANDBOX_STARTUP_GRACE_SEC
        name = f"pp-{uuid.uuid4().hex[:16]}"
        args = prefix + self.docker_args(name, mem, self.settings.SANDBOX_CPUS,
                                         self.settings.SANDBOX_PIDS_LIMIT)

        with self._sem:
            try:
                proc = subprocess.run(args, input=payload, capture_output=True, timeout=host_timeout)
            except subprocess.TimeoutExpired:
                self._force_remove(name)
                raise SandboxInfraError(f"Sandbox container exceeded host timeout ({host_timeout:.0f}s)")
            except OSError as exc:
                raise SandboxInfraError(f"Failed to launch sandbox: {exc}")

        out = proc.stdout
        try:
            resp = json.loads(out.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            err = proc.stderr.decode("utf-8", "replace")[-500:]
            if proc.returncode == 137:
                raise SandboxInfraError("Sandbox container was killed (container memory limit reached "
                                        "or external kill); harness produced no result")
            if "Unable to find image" in err or "No such image" in err:
                raise SandboxUnavailable(f"Sandbox image '{self.image}' not found. Build it first.")
            raise SandboxInfraError(f"Sandbox returned no result (exit {proc.returncode}): {err.strip()}")
        if not resp.get("ok"):
            raise SandboxInfraError(f"Sandbox harness error: {resp.get('error')}")
        return [StepResult.from_json(d) for d in resp["steps"]]

    def self_check(self) -> dict:
        """Return the harness environment report (uid, dumpable flag) — no user code."""
        prefix = self._prefix()
        name = f"pp-{uuid.uuid4().hex[:16]}"
        args = prefix + self.docker_args(name, 64 + self.settings.SANDBOX_MEMORY_OVERHEAD_MB, 0.5, 16)
        r = subprocess.run(args, input=b'{"steps": []}', capture_output=True, timeout=60)
        return json.loads(r.stdout.decode())


_instance: Optional[DockerSandbox] = None
_lock = threading.Lock()


def get_sandbox() -> DockerSandbox:
    global _instance
    with _lock:
        if _instance is None:
            _instance = DockerSandbox()
        return _instance
