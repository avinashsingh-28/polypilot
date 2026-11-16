"""
Compilation service. All compilation happens inside the Docker sandbox.

C++17 : g++ -std=c++17 -O2 -pipe (testlib.h is on the include path).
Python: syntax check via compile() inside the sandbox; the script itself is
        the executable.
"""
import hashlib
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.services.sandbox.driver import DockerSandbox, Step, SandboxUnavailable, SandboxInfraError, get_sandbox

CPP_FLAGS = ["-std=c++17", "-O2", "-pipe"]
LANGUAGE_ALIASES = {
    "cpp": "cpp", "c++": "cpp", "cpp17": "cpp", "c++17": "cpp", "cxx": "cpp", "gnu++17": "cpp",
    "python": "python", "python3": "python", "py": "python", "py3": "python",
}


def normalize_language(lang: Optional[str]) -> Optional[str]:
    if not lang:
        return "cpp"
    return LANGUAGE_ALIASES.get(lang.strip().lower())


@dataclass
class Executable:
    language: str
    payload: bytes          # binary (cpp) or script source (python)
    sha: str

    def materialize(self, role: str) -> Tuple[Dict[str, bytes], List[str], List[str]]:
        """Return (files, cmd, executable_file_names) for this executable under a role name."""
        if self.language == "cpp":
            return {role: self.payload}, [f"./{role}"], [role]
        name = f"{role}.py"
        return {name: self.payload}, ["python3", "-B", name], []


@dataclass
class CompilationResult:
    status: str                     # success | compilation_error | internal_error
    language: str
    version: str
    duration_ms: int
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    executable: Optional[Executable] = field(default=None, repr=False)
    cached: bool = False

    @property
    def success(self) -> bool:
        return self.status == "success"

    def to_dict(self) -> dict:
        return {"status": self.status, "language": self.language, "version": self.version,
                "duration_ms": self.duration_ms, "stdout": self.stdout[:8192],
                "stderr": self.stderr[:16384], "error": self.error, "cached": self.cached}


def _clean_diag(b: bytes) -> str:
    return b.decode("utf-8", "replace").replace("/workspace/", "")


class Compiler:
    _cache: "OrderedDict[str, CompilationResult]" = OrderedDict()
    _cache_lock = threading.Lock()
    _CACHE_MAX = 64

    def __init__(self, sandbox: Optional[DockerSandbox] = None):
        self.sandbox = sandbox or get_sandbox()
        self.settings = get_settings()

    def compile(self, source: str, language: Optional[str]) -> CompilationResult:
        lang = normalize_language(language)
        if lang is None:
            return CompilationResult("internal_error", str(language), "", 0,
                                     error=f"Unsupported language '{language}'. Supported: C++17, Python 3.")
        src = source.encode("utf-8")
        if len(src) > self.settings.MAX_SOURCE_BYTES:
            return CompilationResult("compilation_error", lang, "", 0,
                                     error=f"Source exceeds {self.settings.MAX_SOURCE_BYTES} bytes")
        if not source.strip():
            return CompilationResult("compilation_error", lang, "", 0, error="Source code is empty")
        key = hashlib.sha256(lang.encode() + b"\0" + " ".join(CPP_FLAGS).encode() + b"\0" + src).hexdigest()
        with self._cache_lock:
            hit = self._cache.get(key)
            if hit is not None:
                self._cache.move_to_end(key)
                return CompilationResult(**{**hit.__dict__, "cached": True})

        res = self._compile_cpp(src, key) if lang == "cpp" else self._compile_python(src, key)
        if res.success:
            with self._cache_lock:
                self._cache[key] = res
                while len(self._cache) > self._CACHE_MAX:
                    self._cache.popitem(last=False)
        return res

    def _limits(self):
        s = self.settings
        return dict(time_limit=s.COMPILE_TIMEOUT_SEC, wall_limit=s.COMPILE_TIMEOUT_SEC * 1.5,
                    memory_mb=s.COMPILE_MEMORY_MB)

    def _compile_cpp(self, src: bytes, key: str) -> CompilationResult:
        steps = [
            Step("version", ["g++", "--version"], time_limit=5, memory_mb=128, output_limit=65536),
            Step("compile", ["g++", *CPP_FLAGS, "-o", "prog", "src.cpp"],
                 output_limit=64 * 1024 * 1024, collect=["prog"], **self._limits()),
        ]
        try:
            ver, comp = self.sandbox.execute({"src.cpp": src}, steps)
        except SandboxUnavailable:
            raise                      # nothing executed: callers may retry safely
        except SandboxInfraError as exc:
            return CompilationResult("internal_error", "cpp", "", 0, error=str(exc))
        version = ver.stdout.decode(errors="replace").splitlines()[0] if ver.stdout else "g++ (unknown)"
        version = f"{version} [{' '.join(CPP_FLAGS)}]"
        base = dict(language="cpp", version=version, duration_ms=comp.wall_ms,
                    stdout=_clean_diag(comp.stdout), stderr=_clean_diag(comp.stderr))
        if comp.timed_out:
            return CompilationResult("compilation_error", error=f"Compilation timed out (> {self.settings.COMPILE_TIMEOUT_SEC}s)", **base)
        if comp.memory_exceeded:
            return CompilationResult("compilation_error", error=f"Compiler exceeded {self.settings.COMPILE_MEMORY_MB} MB", **base)
        if comp.clean_exit and "prog" in comp.files:
            return CompilationResult("success", executable=Executable("cpp", comp.files["prog"], key), **base)
        return CompilationResult("compilation_error", error=f"g++ exited with code {comp.exit_code}", **base)

    def _compile_python(self, src: bytes, key: str) -> CompilationResult:
        check = "import sys;compile(open('sol.py','rb').read(),'solution.py','exec')"
        steps = [
            Step("version", ["python3", "--version"], time_limit=5, memory_mb=128, output_limit=65536),
            Step("compile", ["python3", "-B", "-c", check], output_limit=65536, **self._limits()),
        ]
        try:
            ver, comp = self.sandbox.execute({"sol.py": src}, steps)
        except SandboxUnavailable:
            raise                      # nothing executed: callers may retry safely
        except SandboxInfraError as exc:
            return CompilationResult("internal_error", "python", "", 0, error=str(exc))
        version = (ver.stdout or ver.stderr).decode(errors="replace").strip() or "Python 3"
        base = dict(language="python", version=version, duration_ms=comp.wall_ms,
                    stdout=_clean_diag(comp.stdout), stderr=_clean_diag(comp.stderr))
        if comp.clean_exit:
            return CompilationResult("success", executable=Executable("python", src, key), **base)
        return CompilationResult("compilation_error", error="Python syntax check failed", **base)
