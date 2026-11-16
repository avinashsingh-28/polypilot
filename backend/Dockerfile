# PolyPilot backend images (multi-stage).
#   docker build --target api    -t polypilot-api    backend
#   docker build --target worker -t polypilot-worker backend
# The worker only orchestrates sandbox containers; untrusted code never runs in these images.
ARG PYTHON_IMAGE=python:3.12.8-slim-bookworm

FROM ${PYTHON_IMAGE} AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r /tmp/requirements.txt

FROM ${PYTHON_IMAGE} AS base
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LOG_JSON=true
RUN groupadd --gid 10010 app && useradd --uid 10010 --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --from=deps /opt/venv /opt/venv
WORKDIR /srv
COPY --chown=root:root alembic.ini ./
COPY --chown=root:root alembic ./alembic
COPY --chown=root:root app ./app

FROM base AS api
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
# --proxy-headers: client IPs come from the reverse proxy (needed for per-IP auth rate limits).
# FORWARDED_ALLOW_IPS must be the proxy's address/network; never expose this port publicly.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\" --no-server-header"]

FROM docker:27.3.1-cli AS dockercli

FROM base AS worker
# Docker CLI only (no daemon). The worker talks to the host daemon to start locked-down sandboxes.
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --chown=root:root sandbox ./sandbox
USER app
ENV SANDBOX_DOCKER_MODE=native
HEALTHCHECK --interval=60s --timeout=10s --retries=3 CMD ["docker", "version", "--format", "{{.Server.Version}}"]
CMD ["python", "-m", "app.worker"]
