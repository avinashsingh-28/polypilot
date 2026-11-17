# PolyPilot security

## Reporting a vulnerability (responsible disclosure)

Please **do not open a public issue** for security problems. Report privately through GitHub's
"Report a vulnerability" (Security → Advisories) on this repository, or by direct message to the
maintainer. Include the affected version or commit, steps to reproduce, and the impact. Expect an
acknowledgement within 7 days. Please allow up to 90 days for a fix before public disclosure.
Sandbox escapes, authentication/authorization bypasses and credential exposure are the highest
priority. Test only against your own deployment; never against other users' data or real Polygon
problems you do not own.

Legend: **[tested]** = covered by an automated test or an executed check; **[configured]** = set up
but not independently verified; **[gap]** = known limitation.

## Threat model

| Threat | Mitigation | Status |
|---|---|---|
| Malicious C++/Python solution, generator, validator or checker | Runs only in a fresh sandbox container per batch; the API never executes code | [tested] |
| Infinite loop | Per-step CPU rlimit + wall-clock kill by the harness; host-side `docker rm -f` on container timeout | [tested] |
| Memory exhaustion | cgroup `--memory` = `--memory-swap`; peak RSS compared with the limit | [tested] |
| Process exhaustion (fork bomb) | `--pids-limit 64`; stray processes killed after each step | [tested] |
| Output flooding | `RLIMIT_FSIZE` on outputs; truncated capture | [tested] |
| Filesystem access | No bind mounts; read-only root; tmpfs workspace; host paths invisible | [tested] |
| Network access / exfiltration | `--network none`; only loopback exists | [tested] |
| Secret theft | No environment passed to containers; host env var not visible | [tested] |
| Privilege escalation | UID 10001, `--cap-drop ALL`, `no-new-privileges`, Docker default seccomp | [tested: CapEff=0, NoNewPrivs=1, Seccomp=2] |
| Tampering with the harness | Harness is PID 1 (unkillable from inside) and non-dumpable | [tested] |
| Container escape via kernel bug | Shared host kernel (runc). gVisor supported via `SANDBOX_RUNTIME=runsc` | **[gap: gVisor not installed or tested]** |
| AppArmor confinement | Not active on the WSL2 development host | **[gap]** |
| Untrusted code in the same batch | Steps of one job share a UID; a candidate could tamper with another step's files in that batch (result integrity only, not host safety) | **[gap]** |
| Worker compromise | Worker holds the Docker socket (root-equivalent on the host). It runs no user code, has no network port, and runs read-only with caps dropped | **[gap: inherent; use a dedicated VM]** |

**Conclusion:** the sandbox is suitable for code from yourself and trusted collaborators. Accepting
code from the public internet additionally requires gVisor (or VM isolation) on a dedicated host.
Docker alone does not protect against kernel exploits.

## Authentication [tested]

- Argon2id password hashes (`argon2-cffi`). Password rules: 10–128 characters, not trivially
  repetitive, not a common password, must not contain the email name.
- Login creates a random 256-bit session token. It is stored only as SHA-256 in `user_sessions`
  and sent as an `HttpOnly`, `SameSite=Lax`, `Secure` (production) cookie.
- Sessions expire after 24 h idle or 7 days absolute and are revoked on logout. A fresh token is
  issued on every login (no fixation).
- CSRF: `X-CSRF-Token` = HMAC(`AUTH_SECRET_KEY`, session hash), delivered in a readable cookie, is
  required on every POST/PUT/PATCH/DELETE, including logout.
- No account enumeration: registration always returns the same response, and login errors are
  identical for unknown email and wrong password (a dummy hash keeps timing equal).
- Rate limits: 10 auth requests per minute per IP, and 5 failed logins per account per 15 minutes.
  These limits are in memory and per process **[gap: not shared across replicas]**.
- Password reset: `/auth/forgot-password` always returns the same response (no account enumeration),
  is rate limited (per IP, and max 3 emails per address per hour), and issues a single-use token that
  expires after 30 minutes; only its SHA-256 is stored. A new request invalidates older links. A
  successful reset revokes every session. The link token is removed from the browser address bar on
  load. Delivery uses SMTP; without SMTP, development logs the link and production sends nothing.
  **[tested]**
- Not implemented: email verification, MFA. Use `REGISTRATION_OPEN=false` and
  `python -m app.cli create-user` to control who has accounts.

## Authorization [tested]

- Every `/api/v1` route except auth requires a session.
- Every route with `problem_id` or `artifact_id` checks ownership centrally and returns 404 (not
  403) for other users' resources.
- Problem lists are filtered by owner. Polygon credentials, sync history, AI usage, verification
  runs, test cases, counterexamples and repairs are reachable only through the owner's problems.
- A cross-user test covers 16 representative endpoints.
- Legacy problems created before accounts existed are unowned and invisible until claimed.

## Secrets

- Secrets live in `backend/.env` (dev) or `deploy/.env.prod` (server). Both are gitignored, and CI
  runs gitleaks. **[tested: repository and history scan found no secrets]**
- The frontend bundle receives no secrets; CI greps `dist/`.
- Polygon credentials saved from the UI are Fernet-encrypted with `POLYGON_CREDENTIALS_KEY`, are
  never returned by any API, and are per user. Environment Polygon credentials are used in
  production only for the user named in `POLYGON_ENV_CREDENTIALS_EMAIL`.
- Logs never include request bodies, cookies, signatures or keys. The JSON log formatter redacts
  fields whose names look secret.
- If a secret is exposed, rotate it at its source (Gemini key, Polygon key, database password).
  Changing `AUTH_SECRET_KEY` invalidates all CSRF tokens; delete `user_sessions` rows to force
  re-login.

## HTTP hardening [tested]

- 8 MB request cap (413) and validation errors that do not echo submitted values.
- Generic 500 responses with a request ID (no stack traces).
- `nosniff`, `X-Frame-Options: DENY`, `no-referrer`, and a strict CSP at nginx.
- Explicit CORS origins with credentials; startup refuses a wildcard in production.
- OpenAPI/docs are disabled in production; `/metrics` needs `METRICS_TOKEN`.
- The production startup check enforces a strong `AUTH_SECRET_KEY`, `COOKIE_SECURE`, PostgreSQL,
  and https origins.

## Files and uploads [tested]

- Test inputs are text only: no NUL bytes, capped at `MAX_INPUT_BYTES`, stored in PostgreSQL.
- Uploaded file names are reduced to a base name and used only as metadata, never as paths.
- Sandbox file names are matched against `^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$`.
- Polygon file names are generated server-side and validated.
- No API accepts filesystem paths.

## Polygon integration [tested with a mocked Polygon; one live read-only call]

- Requests are signed per the official documentation and sent only to
  `https://polygon.codeforces.com/api`; any other base URL is rejected.
- Writes are never retried blindly. Ambiguous results are checked by reading the remote state back.
- Remote changes not made by PolyPilot are reported as conflicts and never silently overwritten.
- Commit, build, working-copy discard and problem creation each require explicit confirmation
  fields. No access or visibility changes are ever made.
- Every request is recorded in `polygon_operations` without secrets or signatures.

## AI provider [tested with mocks]

- Only server-configured providers are supported; no user-supplied base URLs, so there is no SSRF.
- Each call has a timeout and an output-token cap; prompts are capped at `AI_MAX_PROMPT_CHARS`.
- Only transient errors (429, 5xx, timeouts) are retried, at most twice. Errors are normalized
  into kinds.
- Each user has a daily call quota (`AI_MAX_CALLS_PER_USER_PER_DAY`). Usage rows store sizes only,
  never prompts or responses.
- AI output never triggers privileged actions. Repairs are proposals that the user must accept,
  and accepting only queues a sandboxed re-test.
