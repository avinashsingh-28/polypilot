# Deploying PolyPilot

## Recommended architecture: one Docker VM

The verification worker must start Docker containers with strict security options (`--network none`,
`--cap-drop ALL`, seccomp, cgroup limits; optionally gVisor). Typical PaaS / serverless platforms
(Vercel, Netlify, Render, Railway, Fly.io, Cloud Run, Heroku) **do not give you a Docker daemon**, so
they cannot host the worker safely. Use a plain Linux VM you control:

```
Internet ─► TLS proxy (Caddy / nginx / Cloudflare Tunnel) ─► web:8080 (nginx: SPA + /api proxy)
                                                               └─► backend:8000 (FastAPI)
backend, worker ─► db (PostgreSQL, private network, volume pgdata)
worker ─► host Docker daemon ─► sandbox containers (no network)
```

Everything is defined in `docker-compose.prod.yml`. Only `web` publishes a port, and it binds to
`127.0.0.1:8080` by default so the TLS proxy on the same VM fronts it.

### Sizing and approximate cost

These are approximate list prices from my knowledge and were **not verified live**. Check current
pricing before you buy anything; nothing has been purchased.

| Environment | Setup | Approx. monthly |
|---|---|---|
| Development | Your PC (WSL2 + Docker + local PostgreSQL) | $0 |
| Staging | Small VM (2 vCPU / 4 GB RAM / 40 GB disk), switched on only when needed | $0–6 |
| Production (private / small team) | 2–4 vCPU / 4–8 GB VM (e.g. Hetzner Cloud, DigitalOcean, OVH; Oracle Cloud's Always-Free ARM tier also offers Docker VMs) | ~$5–25 |
| Backups | Provider snapshots or off-site object storage for `pg_dump` files | ~$1–3 |
| TLS / domain | Let's Encrypt (free) + a domain | ~$1 |
| AI | Gemini usage, bounded by `AI_MAX_CALLS_PER_USER_PER_DAY` | usage-based; tests use $0 |

A managed PostgreSQL is optional. The bundled container with daily `pg_dump` backups is enough for
private use.

## Environment variables (`deploy/.env.prod`)

Copy `deploy/.env.prod.example`. The required and important variables:

| Variable | Purpose |
|---|---|
| `ENVIRONMENT=production` | Enables production checks: docs off, strict config validation |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Database credentials (long random password) |
| `AUTH_SECRET_KEY` | ≥ 32 random characters (`python -c "import secrets;print(secrets.token_urlsafe(48))"`) |
| `COOKIE_SECURE=true`, `COOKIE_SAMESITE=lax` | Cookie flags (HTTPS required) |
| `CORS_ORIGINS=["https://your.domain"]` | Exact https origin(s); no wildcard |
| `REGISTRATION_OPEN` | `false` for private deployments; create accounts with the CLI |
| `METRICS_TOKEN` | Bearer token for `/metrics` (internal scraping only) |
| `GEMINI_API_KEY`, `AI_MODEL`, `AI_MAX_CALLS_PER_USER_PER_DAY` | AI provider |
| `PUBLIC_APP_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Forgot-password emails (any SMTP provider). Without SMTP, production cannot send reset links |
| `POLYGON_CREDENTIALS_KEY` | Fernet key for per-user Polygon credentials saved in the UI |
| `POLYGON_API_KEY`, `POLYGON_API_SECRET`, `POLYGON_ENV_CREDENTIALS_EMAIL` | Optional shared env credentials, usable only by that one user |
| `SANDBOX_MAX_CONCURRENT`, `MAX_*` | Execution limits (server maxima) |
| `SANDBOX_RUNTIME=runsc` | Run sandboxes under gVisor (strongly recommended for any multi-user use) |
| `DOCKER_GID` | Host docker group id (`getent group docker \| cut -d: -f3`) |

The backend refuses to start in production if the critical variables are unsafe.

## First deployment

```bash
# On the VM (Ubuntu 24.04 example) — as a non-root sudo user
curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER   # re-login afterwards
sudo git clone <your repo> /opt/polypilot && sudo chown -R $USER /opt/polypilot && cd /opt/polypilot
cp deploy/.env.prod.example deploy/.env.prod && chmod 600 deploy/.env.prod && nano deploy/.env.prod
docker build -t polypilot-sandbox:latest backend/sandbox
docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod exec backend python -m app.cli create-user --email you@example.com
```

Migrations run automatically through the `migrate` one-shot service (`alembic upgrade head`) before
the API and worker start. Migrations in this repository are additive. Review any new migration
before deploying it, and never run `alembic downgrade` in production without a fresh backup.

Optional gVisor (recommended): install `runsc` following the gVisor documentation, register it as a
Docker runtime, then set `SANDBOX_RUNTIME=runsc` and run `docker compose … up -d worker`.
Verify with `docker compose … exec worker python -m app.worker --check`.

TLS: put Caddy in front, e.g. a `Caddyfile` containing `your.domain { reverse_proxy 127.0.0.1:8080 }`.

## Health checks

| Endpoint | Meaning |
|---|---|
| `GET /health` | Process alive (liveness) |
| `GET /health/ready` | Database reachable (readiness; 503 otherwise) |
| `GET /health/worker` | At least one worker heartbeat in the last 60 s; includes sandbox availability and queue length (503 if none) |
| `GET /metrics` (with `Authorization: Bearer $METRICS_TOKEN`) | Prometheus text: request counts and latency, error counts, worker and run gauges |

`/metrics` is not proxied by nginx. Scrape it from the VM: `docker compose exec backend curl …`.

## Backups and restore

`deploy/backup.sh` writes a verified `pg_dump -Fc` file to `/var/backups/polypilot` and keeps 14 of
them. Schedule it with cron (example in the script header) and copy the directory off the VM
(object storage or another machine).

Restore always goes into a **new** database first:
```bash
DC="docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod"
$DC exec -T db psql -U polypilot -d postgres -c "CREATE DATABASE polypilot_restore"
$DC exec -T db pg_restore -U polypilot -d polypilot_restore --no-owner < /var/backups/polypilot/<file>.dump
# verify counts, then point POSTGRES_DB at it (or rename databases) and restart backend + worker
```
This exact dump → restore → row-count comparison was executed against the compose stack (all tables
matched, schema version preserved).

Retention: `python -m app.cli prune --days 90` deletes expired sessions and old Polygon request logs,
AI usage rows and stale heartbeats. Use `--dry-run` first.

## CI/CD

- `.github/workflows/ci.yml` runs on every PR and every push to `main`:
  - ruff
  - pip-audit
  - the sandbox image build plus pytest (including the Docker sandbox tests)
  - the migration upgrade/downgrade/upgrade cycle on a fresh PostgreSQL
  - the end-to-end evaluation
  - the frontend lint, build and `npm audit`
  - Docker image builds plus a non-root check
  - gitleaks
- `.github/workflows/deploy.yml` is manual (`workflow_dispatch`) and limited to tags or commit SHAs.
  It requires a protected `production` environment with reviewers. It backs up first, deploys over
  SSH and checks health. Application secrets stay on the server.

## Troubleshooting

| Symptom | Check |
|---|---|
| Runs stay `queued` | `curl localhost:8080/health/worker`; `docker compose logs worker` |
| `sandbox_available: false` | The sandbox image isn't built on the host, or `DOCKER_GID` is wrong |
| Backend exits on start | Log says `Refusing to start in production: …`; fix the listed variables |
| 401 after login over plain http | `COOKIE_SECURE=true` requires HTTPS |
| All logins rate-limited | Proxy not forwarding client IPs (see `FORWARDED_ALLOW_IPS`) |
| Polygon errors | Settings → Polygon → Test connection; the error kind is shown |
