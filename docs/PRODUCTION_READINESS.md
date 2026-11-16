# Production-readiness assessment (Phase 6)

**Classification: Staging-ready.**
Private production use (you plus trusted collaborators, on your own VM with TLS) is reasonable after
the steps in *Before private production*. **Public multi-user use is blocked** (see *Blockers*).

## Audit findings and resolution

| Sev. | Finding | Resolution |
|---|---|---|
| Critical | No authentication; every API was open | Accounts, sessions, CSRF, rate limits — **fixed, tested** |
| Critical | No authorization; any caller could read or modify any problem, credentials or jobs | Central ownership enforcement, per-user Polygon credentials — **fixed, tested (16-endpoint IDOR suite)** |
| Critical | Shared Polygon credentials usable by anyone | Per-user encrypted credentials; env credentials restricted in production — **fixed, tested** |
| High | AI calls blocked the event loop, had no timeout and retried every error | Async client, timeout, output cap, transient-only retries — **fixed, unit-tested** |
| High | AI specification not validated (a malformed model output flowed into later steps) | Structured-output validation → `invalid_response` — **fixed, tested** |
| High | No per-user AI limits | Daily quota + usage records (no content) — **fixed, tested** |
| High | Unbounded job queue (per-problem limit only) | Per-user active-run limit (429) + global queue cap (503) — **fixed, tested** |
| High | Verification gate blamed every artifact a failed run compiled (a wrong candidate blocked the generator upload) | Failure attribution per role — **fixed, regression-tested** (found by the E2E evaluation) |
| High | Generation jobs stuck in `running` after a restart | Startup recovery — **fixed** (reviewed, not covered by an automated test) |
| High | `/health/db` leaked exception text; no readiness or worker health | Sanitized; `/health/ready`, `/health/worker`, `/metrics` — **fixed, tested** |
| High | Hard-coded dev API URL. Your local `frontend/.env.local` pointed cross-origin, which breaks cookie sessions | Same-origin `/api/v1` + Vite/nginx proxy; `.env.local` line commented out (backup kept) — **fixed, tested** |
| High | Frontend faked a local problem when saving failed | Removed — **fixed** |
| High | `package-lock.json` out of sync (clean installs failed) | Regenerated — **fixed** |
| High | Critical advisories: DOMPurify (via Monaco), Vitest/Tinypool | DOMPurify override 3.4.17, Vitest 4.1.12 — **fixed, `npm audit`: 0** |
| High | No CI, containers or deployment docs | Added (CI **not yet run on GitHub**) |
| Medium | Database outages surfaced as generic 500s | 503 + `Retry-After` — **fixed, tested** |
| Medium | Runs that failed because the sandbox was down could not recover | One safe re-queue when nothing executed — **fixed, tested** |
| Medium | Schema drift (`problems.idea` NOT NULL) broke problem creation on PostgreSQL | Migration 0007 — **fixed** |
| Medium | nginx dropped security headers on SPA routes | Fixed (found by the compose smoke test) — **tested** |
| Medium | Sandbox base image unpinned; DB pool unbounded | Digest pin; pool and timeouts — **configured** |
| Medium | AI Providers page showed mock data and a fake key form | Real server status — **fixed** |
| Low | Unbounded logs, sessions and usage rows | `app.cli prune` — **added** |
| Low | Search box placeholder | Disabled and labelled "not implemented" |
| Checked, no issue | SQL injection (ORM / bound parameters only), XSS sinks (none: no `innerHTML`; React escaping), SSRF (fixed Polygon host; no user-supplied AI URLs), exception text in responses | — |

## Evidence (all actually executed)

| Check | Result |
|---|---|
| Backend `pytest` (unit, API, security, Polygon mocks, real Docker sandbox incl. malicious programs) | **116 passed** |
| Frontend `vitest` (API client: CSRF, credentials, 401 handling, honest errors) | **8 passed** |
| `ruff` / `tsc -b` | clean / clean |
| `pip-audit` / `npm audit` | 0 / 0 vulnerabilities |
| Secret scan (152 committable files + git history) | no secrets; no `.env` ever committed |
| Migrations up → downgrade base → up, fresh PostgreSQL 16 | passed (7 revisions) |
| E2E evaluation (mock AI, mock Polygon, real sandbox + PostgreSQL) | **24 passed, 0 failed, 1 not implemented** (checker generation) |
| Docker builds (api, worker, web, sandbox) | built; all run as non-root |
| Production compose stack smoke test | health/ready/worker OK; Secure+HttpOnly cookie; CSRF; containerized worker compiled in the sandbox; metrics token; DB not published; docs off; logout revokes |
| Backup → restore into a new database | all table counts matched |
| Load test (20 concurrent, single API process on WSL2) | `/health` 712 req/s · `/health/ready` 209 req/s · authenticated list 97 req/s (p95 340 ms) · 0 errors |
| Dev path (Vite proxy → API) | login, CSRF write, logout verified with curl |
| Live Polygon | read-only connection test only; **no live writes** |
| Live AI | not exercised in Phase 6 |
| GitHub Actions | written + YAML-validated; **not run on GitHub** |
| Browser UI | build passes; **not manually exercised in a browser** |

## End-to-end workflow (requested steps)

| # | Step | Result |
|---|---|---|
| 1–2 | Create problem, enter idea | Passed |
| 3 | Generate structured specification | Passed (mock AI, real pipeline + schema validation) |
| 4–5 | Statement, editorial, reference, brute force | Passed |
| 6 | Validator and generator | Passed |
| 6 | **Checker** | **Not implemented** (token comparison; uploaded testlib checkers are supported) |
| 7–9 | Compile, generate + validate tests, run reference | Passed (real sandbox) |
| 10–11 | Differential testing; wrong (WA) and slow (TLE) solutions | Passed |
| 12 | Counterexample captured and minimized | Passed (`8 numbers` → `1\n-1\n`, every reduction validator-checked) |
| 13–14 | Review package, sync to Polygon | Passed against **mock** Polygon; live: **blocked** (needs your approval and a throwaway problem) |
| 15–17 | Commit, build, verify real result | Passed against **mock** Polygon; live: **blocked** |

## Checklist

| Area | Status | Notes |
|---|---|---|
| Frontend | Incomplete | Auth gate, real data, honest errors, lazy loading done. Missing: artifact editing/saving UI, per-step regenerate button, screenshots, manual browser/responsive pass |
| Backend | Complete | Hardened; 116 tests |
| PostgreSQL | Complete | Pooling, timeouts, indexes, migrations, backup/restore tested. Legacy problems still need claiming |
| Authentication | Incomplete | Core complete; password reset, email verification, MFA not implemented |
| Authorization | Complete | Central ownership checks; IDOR suite |
| AI integration | Incomplete | Hardened and mock-tested; not exercised live in Phase 6; checker generation missing |
| Code execution | Complete | C++17 / Python 3, verdicts, limits |
| Sandbox security | Incomplete | All container restrictions tested. **gVisor/VM isolation not installed — blocks public use** |
| Worker reliability | Complete | States, heartbeat, crash recovery, cancellation, bounded queues, safe infra retry, idempotency keys |
| Polygon integration | Incomplete | Mock-tested end to end. Live writes blocked pending your approval |
| Automated testing | Incomplete | Suites exist and pass locally; CI not yet run on GitHub; no formatter check (not enforced, to avoid a mass reformat) |
| Deployment | Incomplete | Images, compose and docs ready and tested locally; no real VM/TLS yet (nothing purchased) |
| Monitoring | Complete | JSON logs, request IDs, health endpoints, metrics. Alerting: choose with the host |
| Documentation | Complete | README, docs/ARCHITECTURE, SECURITY (+ disclosure), DEPLOYMENT, USER_GUIDE, this file |

## Blockers for public multi-user deployment

1. **Kernel-level isolation:** sandboxes share the host kernel (runc + seccomp). Install gVisor
   (`SANDBOX_RUNTIME=runsc`) or use microVMs on a dedicated host, then re-run the sandbox tests.
2. **Worker holds the Docker socket** (root-equivalent). Acceptable only on a dedicated VM.
3. **No account recovery or email verification**; abuse controls are limited to rate limits and
   quotas.
4. **In-memory rate limits:** run a single API process or move the limiter to a shared store.

## Before private production

1. Deploy to a VM with TLS. Set `ENVIRONMENT=production` and `REGISTRATION_OPEN=false`, and create
   accounts with `python -m app.cli create-user`.
2. Run `python -m app.cli claim-problems --email <you>`.
3. Push to GitHub, make CI green, and protect the `production` environment.
4. Schedule `deploy/backup.sh` and copy the backups off-site.
5. With your approval, run the live Polygon E2E on a throwaway problem
   (`python -m scripts.e2e_eval --live-polygon-id <id>`, then `--approve-upload`, `--approve-commit`
   and `--approve-build` one step at a time).
6. Recommended: install gVisor.
