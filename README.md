# PolyPilot 🧭

> **From problem idea to a verified Codeforces Polygon package.**
> An AI-assisted problem-setting platform for competitive programming.

## What problem it solves

Preparing a Codeforces-style problem means writing and cross-checking a statement, an editorial,
a reference solution, a brute-force solution, a `testlib.h` validator, generators, tests, and
deliberately wrong/slow solutions — and then uploading all of it to Polygon by hand.

PolyPilot drafts these artifacts with an AI model, **verifies them by actually running them** in an
isolated Docker sandbox, and synchronizes the verified package to Polygon through the official API.
Generated code is treated as untrusted: nothing is assumed correct because it was generated.

## Key features

| Area | What exists today |
|---|---|
| Accounts | Email + password accounts (Argon2id), HttpOnly session cookies, CSRF protection, per-user data isolation |
| Generation | Spec → statement → editorial → reference → brute force → validator → generator (Gemini; mocked in tests) |
| Sandbox | Every compile/run in a fresh locked-down container: no network, read-only root, non-root, caps dropped, seccomp, CPU/memory/PID/output/time limits |
| Verification | Validator tests (valid + invalid inputs), generator runs with seeds, reference runs, differential testing, stress testing, WA/TLE candidate classification, counterexample minimization |
| Repair | User-triggered AI repair proposals, stored as separate versions, re-tested before being trusted |
| Polygon | Signed official-API client, link/create problem, preview, dry run, upload to working copy, explicit commit, explicit package build with real status |
| Operations | Health/readiness/worker endpoints, Prometheus metrics, JSON logs with request IDs, admin CLI, backups |

Not implemented: password reset / email verification, multiple AI providers, statement images,
Polygon test scripts and test groups, search. See [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md).

## Architecture

```
Browser ──HTTPS──► nginx (static SPA + /api proxy) ──► FastAPI API ──► PostgreSQL
                                                          ▲
                              verification worker ────────┘  (polls queued jobs)
                                     │ Docker API
                                     ▼
                         sandbox container per batch (untrusted code)
```

The API never executes user code. Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Technology

React 19 + TypeScript + Vite · FastAPI · SQLAlchemy 2 + Alembic · PostgreSQL 16 · Docker
(Alpine sandbox with g++ 13 / Python 3.12 and `testlib.h`) · Google Gemini · Codeforces Polygon API.

## Local development (Windows + WSL2, or Linux/macOS)

Prerequisites: Python 3.12, Node 22, PostgreSQL 16, Docker (inside WSL2 on Windows).

```powershell
# 1. Backend
cd backend
python -m venv venv; .\venv\Scripts\pip install -r requirements-dev.txt
copy .env.example .env          # then edit: database password, GEMINI_API_KEY, ...
.\venv\Scripts\python -m alembic upgrade head

# 2. Sandbox image (once, and after changing backend/sandbox)
wsl -d Ubuntu-22.04 -- docker build -t polypilot-sandbox:latest backend/sandbox
.\venv\Scripts\python -m app.worker --check

# 3. Run (three terminals)
.\venv\Scripts\python -m uvicorn app.main:app --reload     # API on :8000
.\venv\Scripts\python -m app.worker                        # verification worker
cd ..\frontend; npm ci; npm run dev                        # UI on http://localhost:5173 (proxies /api)
```

Open http://localhost:5173, register, sign in. Do **not** set `VITE_API_URL` for local development:
the Vite proxy keeps the API same-origin, which the session cookie requires. Problems created before accounts existed are
unowned; assign them with `python -m app.cli claim-problems --email you@example.com`.

## Tests

```powershell
cd backend
.\venv\Scripts\python -m ruff check .
.\venv\Scripts\python -m pytest              # sandbox tests auto-skip without Docker
.\venv\Scripts\python -m scripts.e2e_eval    # end-to-end: mock AI + mock Polygon, real sandbox + PostgreSQL
cd ..\frontend; npm run lint; npm test; npm run build; npm audit
```

On Windows, run `npm test` from PowerShell (a `C:\...` path). Vitest 4 fails to start when the
working directory uses a lowercase drive letter (`c:/...`, which Git Bash produces).

No test makes paid AI calls or live Polygon writes.

Screenshots: not included yet (the UI has not been captured since the Phase 6 changes).

## Deployment

A single Docker VM running `docker-compose.prod.yml` (PostgreSQL, API, worker, nginx) behind TLS.
See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Security model: [docs/SECURITY.md](docs/SECURITY.md).
Problem-setter guide: [docs/USER_GUIDE.md](docs/USER_GUIDE.md).
