"""
Real Docker sandbox tests (skipped automatically when Docker/the image is unavailable).
These execute deliberately hostile programs ONLY inside the sandbox container.
"""
import os

import pytest

from app.services.sandbox import Compiler, get_sandbox, run_program
from app.services.sandbox import runner as R

pytestmark = pytest.mark.sandbox

_status = None


def _available():
    global _status
    if _status is None:
        try:
            _status = get_sandbox().status()
        except Exception:
            _status = {"available": False}
    return _status["available"]


@pytest.fixture(scope="module", autouse=True)
def require_sandbox():
    if not _available():
        pytest.skip("Docker sandbox not available")


def cpp(src):
    res = Compiler().compile(src, "cpp")
    assert res.success, res.stderr
    return res.executable


def py(src):
    res = Compiler().compile(src, "python")
    assert res.success, res.stderr
    return res.executable


def run(exe, inp="", tl=2.0, mem=256, out=1 << 20, expected=None):
    return run_program(exe, inp, tl, mem, out, expected=expected)


# ── Compilation ──────────────────────────────────────────────────────────────
def test_compile_success_reports_version():
    res = Compiler().compile("#include <cstdio>\nint main(){puts(\"hi\");}", "cpp")
    assert res.status == "success" and "g++" in res.version and "-std=c++17" in res.version


def test_compile_error_preserves_diagnostics_without_host_paths():
    res = Compiler().compile("int main(){ undefined_symbol(); }", "cpp")
    assert res.status == "compilation_error"
    assert "undefined_symbol" in res.stderr and "/workspace/" not in res.stderr
    assert "Users" not in res.stderr and "avina" not in res.stderr


def test_python_syntax_error():
    res = Compiler().compile("def f(:\n  pass", "python")
    assert res.status == "compilation_error"


def test_testlib_available():
    res = Compiler().compile('#include "testlib.h"\nint main(int c,char**v){registerValidation(c,v);inf.readInt();inf.readEoln();inf.readEof();}', "cpp")
    assert res.success, res.stderr


# ── Execution statuses ───────────────────────────────────────────────────────
def test_accepted_requires_expected_output():
    exe = cpp("#include <cstdio>\nint main(){int a,b;scanf(\"%d%d\",&a,&b);printf(\"%d\\n\",a+b);}")
    assert run(exe, "2 3\n").status == R.EXECUTED          # no expected → not "Accepted"
    assert run(exe, "2 3\n", expected="5").status == R.ACCEPTED
    assert run(exe, "2 3\n", expected="  5 \n\n").status == R.ACCEPTED
    r = run(exe, "2 3\n", expected="6")
    assert r.status == R.WRONG_ANSWER and r.comparison["expected_token"] == "6"


def test_runtime_error_segfault():
    r = run(cpp("int main(){ volatile int* p = nullptr; *p = 1; }"))
    assert r.status == R.RUNTIME_ERROR and "SIGSEGV" in r.error_details


def test_runtime_error_nonzero_exit():
    r = run(cpp("int main(){ return 3; }"))
    assert r.status == R.RUNTIME_ERROR and r.exit_code == 3


def test_cpu_timeout():
    r = run(cpp("int main(){ volatile unsigned long long x=0; for(;;) x++; }"), tl=1.0)
    assert r.status == R.TLE and r.time_ms >= 900
    assert r.wall_ms < 5000


def test_idle_timeout_is_flagged_inconclusive():
    r = run(py("import time\ntime.sleep(30)"), tl=0.5)
    assert r.status == R.TLE and r.wall_timed_out and "inconclusive" in r.error_details


def test_memory_limit_exceeded():
    src = "#include <cstdlib>\nint main(){ size_t n=400u<<20; volatile char* p=(volatile char*)malloc(n); if(!p) return 7; for(size_t i=0;i<n;i+=4096) p[i]=1; return p[n-4096]-1; }"
    r = run(cpp(src), mem=128)
    assert r.status == R.MLE, (r.status, r.error_details, r.peak_memory_kb)


def test_peak_memory_measured():
    src = "#include <vector>\n#include <cstdio>\nint main(){ std::vector<char> v(64<<20, 1); volatile char* q=v.data(); for(size_t i=0;i<v.size();i+=4096) q[i]=2; printf(\"%d\\n\", q[12288]); }"
    r = run(cpp(src), mem=256)
    assert r.status == R.EXECUTED and r.peak_memory_kb >= 60 * 1024


def test_output_limit():
    r = run(cpp("#include <cstdio>\nint main(){ for(;;) puts(\"spam spam spam spam\"); }"), out=1 << 16, tl=3)
    assert r.status == R.OUTPUT_LIMIT
    assert len(r.stdout) <= 1 << 16


# ── Malicious programs (sandbox isolation) ───────────────────────────────────
def test_no_host_filesystem_access():
    code = r'''
import os
paths = ["/mnt/c", "/mnt/c/Windows/win.ini", "/host", "/var/run/docker.sock", "/run/docker.sock"]
print(" ".join("EXISTS:" + p for p in paths if os.path.exists(p)) or "NONE")
'''
    r = run(py(code))
    assert r.status == R.EXECUTED and r.stdout.strip() == "NONE"


def test_no_environment_secrets(monkeypatch):
    monkeypatch.setenv("POLYPILOT_SECRET_PROBE", "leak-me-123")
    r = run(py("import os\nprint(sorted(os.environ.items()))"))
    assert "leak-me-123" not in r.stdout and "GEMINI" not in r.stdout and "POSTGRES" not in r.stdout
    assert "PATH" in r.stdout


def test_network_disabled():
    code = r'''
import socket
try:
    socket.create_connection(("1.1.1.1", 53), timeout=2); print("CONNECTED")
except OSError as e:
    print("BLOCKED")
print(sorted(i[1] for i in socket.if_nameindex()))
'''
    r = run(py(code), tl=5)
    assert "BLOCKED" in r.stdout and "CONNECTED" not in r.stdout
    assert "eth0" not in r.stdout


def test_fork_bomb_is_contained():
    code = r'''
import os, time
n = 0
try:
    while n < 10000:
        if os.fork() == 0:
            time.sleep(30); os._exit(0)
        n += 1
except OSError:
    pass
print(n)
'''
    r = run(py(code), tl=3)
    assert r.stdout.strip() and int(r.stdout.split()[0]) < 64
    # sandbox remains usable afterwards (strays were killed with the container)
    assert run(py("print(1)")).stdout.strip() == "1"


def test_unprivileged_and_restricted():
    code = r'''
import os
st = dict(l.split(":", 1) for l in open("/proc/self/status").read().splitlines() if ":" in l)
print(os.getuid(), st["CapEff"].strip(), st["NoNewPrivs"].strip(), st["Seccomp"].strip())
try:
    open("/usr/bin/evil", "w"); print("ROOTFS_WRITABLE")
except OSError:
    print("ROOTFS_READONLY")
try:
    open("/proc/1/environ").read(); print("HARNESS_READABLE")
except OSError:
    print("HARNESS_PROTECTED")
print(sorted(os.listdir("/dev")))
'''
    r = run(py(code))
    first = r.stdout.split("\n")[0].split()
    assert first[0] == "10001"                    # non-root
    assert int(first[1], 16) == 0                 # no effective capabilities
    assert first[2] == "1"                        # no_new_privs
    assert first[3] == "2"                        # seccomp filter active
    assert "ROOTFS_READONLY" in r.stdout and "HARNESS_PROTECTED" in r.stdout
    for dev in ("sda", "nvme0n1", "kvm", "mem", "kmsg"):
        assert f"'{dev}'" not in r.stdout


def test_cannot_kill_harness():
    r = run(py("import os, signal\ntry:\n os.kill(1, signal.SIGKILL)\nexcept Exception as e:\n print('ERR', e)\nprint('alive')"))
    assert r.status == R.EXECUTED and "alive" in r.stdout


def test_no_host_side_effects():
    marker = os.path.join(os.path.expanduser("~"), "polypilot_sandbox_escape_marker")
    run(py(f"open({marker!r}, 'w').write('x')"))
    assert not os.path.exists(marker)
