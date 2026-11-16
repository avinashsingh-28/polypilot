# PolyPilot architecture

## Services

| Service | Code | Runs untrusted code? | Network exposure |
|---|---|---|---|
| Frontend (SPA) | `frontend/` — React 19, Vite | no | public via nginx |
| nginx | `frontend/nginx.conf` | no | public (TLS terminated in front of it) |
| API | `backend/app/main.py` — FastAPI | **never** | internal only (behind nginx) |
| Worker | `backend/app/worker.py` | no — it starts sandbox containers | none (no listening port) |
| Sandbox | `backend/sandbox/` (`harness.py` + Alpine image) | **yes** | none (`--network none`) |
| PostgreSQL | — | no | internal only |

External services: Google Gemini (generation, repair proposals), Codeforces Polygon API.

## Data flow

1. The browser talks only to its own origin. `/api/*` is proxied to FastAPI; session cookies are first-party.
2. Every `/api/v1` route except `/auth/*` requires a session (`app/api/deps.py: require_user`).
   `enforce_ownership` resolves any `problem_id` / `artifact_id` path parameter and returns 404
   unless the problem belongs to the caller. Unsafe methods also require the CSRF header.
3. **Generation** (`app/services/generation`) runs as an in-process async task in the API: it only
   calls the AI provider and stores text artifacts. It never compiles or runs code.
   Interrupted jobs are marked failed at API startup.
4. **Verification**: the API inserts a `verification_runs` row (`queued`). The worker claims it with
   `SELECT … FOR UPDATE SKIP LOCKED`, sets `running`, heartbeats, and executes it through
   `app/services/verification/engine.py`. Results, counterexamples and logs go to PostgreSQL.
5. **Sandbox**: `app/services/sandbox/driver.py` runs `docker run` for one batch of steps. Source and
   inputs travel as JSON on stdin; no host directory is mounted. The trusted harness (PID 1 in the
   container) applies per-step rlimits and timeouts and returns JSON results.
6. **Polygon** (`app/services/polygon`): the API signs requests on the backend, plans changes with
   read-only calls (dry run), uploads approved changes to the user's Polygon working copy, and only
   commits/builds on explicit user requests. Every request is logged without secrets.

## Backend layout

```
app/api/routes/   auth, problems, artifacts, generation, verification, polygon, ai, health
app/api/deps.py   authentication + ownership dependencies
app/core/         config, security (Argon2, sessions, CSRF, rate limiter), observability
app/models/       SQLAlchemy models
app/services/ai/  provider abstraction, Gemini provider, usage tracking/quota
app/services/sandbox/        Docker driver, compiler, runner/judge, token comparator
app/services/verification/   engine, config clamping, minimizer, AI repair
app/services/polygon/        signed client, credentials, mapping, sync engine
app/worker.py     verification worker      app/cli.py   admin CLI
scripts/e2e_eval.py          end-to-end evaluation
```

## Database (PostgreSQL, Alembic migrations 0001–0007)

- `users`, `user_sessions` (SHA-256 of session token only), `problems.owner_id → users`
- `problem_artifacts` (versioned text artifacts), `generation_jobs`
- `test_cases` (validation status, generation metadata), `verification_runs` (status, config,
  progress, report, logs, heartbeat, idempotency key), `counterexamples`, `solution_repairs`
- `problem_integrations` (Polygon link + revision/commit/build state), `polygon_accounts`
  (per-user, Fernet-encrypted credentials), `polygon_sync_runs`, `polygon_operations` (request log),
  `polygon_item_states` (last confirmed remote state per item)
- `worker_heartbeats`, `ai_usage` (sizes/outcomes only, no content)

All child tables cascade on problem deletion. Migrations are additive; the full
upgrade → downgrade base → upgrade cycle is tested in CI on a fresh database.

## Verification workflow

| Run type | What happens |
|---|---|
| `compile` | Compile one artifact (C++17 `g++ -O2` or Python syntax check) |
| `validator` | Validator must accept all valid tests and reject `invalid` tests + 5 generated malformed inputs |
| `generate` | `gen <type> <seed> [args]` per seed, every output validated, duplicates skipped |
| `reference` | Reference on all valid tests; judged by checker or token comparison when an answer exists |
| `differential` / `stress` | gen → validate → reference + candidate → compare, per seed; mismatches saved and minimized |
| `candidate` | Classify a solution (AC/WA/TLE/MLE/RE); TLE re-run to confirm |

Accepted is only reported after comparison with an expected answer or a checker.
