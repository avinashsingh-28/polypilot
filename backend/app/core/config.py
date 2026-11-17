from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Project metadata
    PROJECT_NAME: str = "PolyPilot Backend"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # PostgreSQL connection settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "polypilot"
    POSTGRES_USER: str = "polypilot_user"
    POSTGRES_PASSWORD: str = ""
    DATABASE_URL: Optional[str] = None

    # Database pool
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT_SEC: int = 10
    DB_CONNECT_TIMEOUT_SEC: int = 5
    DB_STATEMENT_TIMEOUT_MS: int = 30000

    # AI Provider settings
    AI_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    AI_MODEL: str = "gemini-3.5-flash"
    AI_TIMEOUT_SEC: float = 120.0
    AI_MAX_RETRIES: int = 2                    # transient errors only (429/5xx/timeouts)
    AI_MAX_OUTPUT_TOKENS: int = 8192
    AI_MAX_PROMPT_CHARS: int = 60000
    AI_MAX_CALLS_PER_USER_PER_DAY: int = 200

    # ── Phase 4: sandbox & verification limits (server-side maxima) ─────────
    SANDBOX_IMAGE: str = "polypilot-sandbox:latest"
    SANDBOX_DOCKER_MODE: str = "auto"          # auto | native | wsl
    SANDBOX_WSL_DISTRO: str = "Ubuntu-22.04"
    SANDBOX_MAX_CONCURRENT: int = 2            # concurrent containers per worker
    SANDBOX_CPUS: float = 1.0
    SANDBOX_PIDS_LIMIT: int = 64
    SANDBOX_WORKSPACE_MB: int = 128
    SANDBOX_MEMORY_OVERHEAD_MB: int = 96       # harness + tmpfs headroom
    SANDBOX_STARTUP_GRACE_SEC: float = 30.0
    SANDBOX_RUNTIME: str = ""                  # e.g. "runsc" to run sandboxes under gVisor (optional)
    COMPILE_TIMEOUT_SEC: float = 30.0
    COMPILE_MEMORY_MB: int = 1024
    DEFAULT_TIME_LIMIT_SEC: float = 2.0
    MAX_TIME_LIMIT_SEC: float = 10.0
    MAX_MEMORY_MB: int = 1024
    MAX_OUTPUT_BYTES: int = 16 * 1024 * 1024
    MAX_INPUT_BYTES: int = 2 * 1024 * 1024     # max stored test input
    MAX_SOURCE_BYTES: int = 256 * 1024
    MAX_STRESS_ITERATIONS: int = 2000
    MAX_GENERATED_TESTS: int = 200
    MAX_JOB_DURATION_SEC: int = 1800
    MAX_ACTIVE_RUNS_PER_PROBLEM: int = 3
    MAX_ACTIVE_RUNS_PER_USER: int = 6          # queued + running across all of a user's problems
    MAX_QUEUED_RUNS_TOTAL: int = 200           # global queue bound (back-pressure: HTTP 503)
    INFRA_RETRY_LIMIT: int = 1                 # re-queue a run whose sandbox was unavailable (nothing executed)
    MAX_LOG_BYTES: int = 64 * 1024
    WORKER_POLL_INTERVAL_SEC: float = 2.0
    WORKER_STALE_AFTER_SEC: int = 300
    WORKER_HEARTBEAT_STALE_SEC: int = 60

    # ── Phase 5: Polygon API ────────────────────────────────────────────────
    # Env credentials take precedence over credentials saved via the UI (stored Fernet-encrypted,
    # which requires POLYGON_CREDENTIALS_KEY). The base URL is restricted to polygon.codeforces.com.
    POLYGON_API_KEY: str = ""
    POLYGON_API_SECRET: str = ""
    POLYGON_API_BASE_URL: str = "https://polygon.codeforces.com/api"
    POLYGON_CREDENTIALS_KEY: str = ""
    POLYGON_TIMEOUT_SEC: float = 60.0
    POLYGON_MIN_INTERVAL_SEC: float = 0.25
    POLYGON_STATEMENT_LANG: str = "english"
    POLYGON_TESTSET: str = "tests"
    # Env credentials are a single shared Polygon account. In production they are only used for
    # the user with this email; in development they apply to every local user.
    POLYGON_ENV_CREDENTIALS_EMAIL: str = ""

    # ── Phase 6: authentication & HTTP hardening ─────────────────────────────
    AUTH_SECRET_KEY: str = ""                  # required in production (>= 32 chars)
    SESSION_COOKIE_NAME: str = "pp_session"
    CSRF_COOKIE_NAME: str = "pp_csrf"
    SESSION_IDLE_TIMEOUT_MIN: int = 24 * 60
    SESSION_ABSOLUTE_TIMEOUT_DAYS: int = 7
    COOKIE_SECURE: bool = False                # must be true in production (HTTPS)
    COOKIE_SAMESITE: str = "lax"
    REGISTRATION_OPEN: bool = True
    # Password reset (forgot password). Without SMTP_HOST, development prints the reset link to the
    # backend log; production cannot send resets until SMTP is configured.
    PUBLIC_APP_URL: str = "http://localhost:5173"
    PASSWORD_RESET_TTL_MIN: int = 30
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_STARTTLS: bool = True
    AUTH_RATE_LIMIT_PER_MIN: int = 10          # per client IP, auth endpoints
    AUTH_MAX_FAILURES_PER_EMAIL: int = 5       # per 15 minutes
    MAX_REQUEST_BYTES: int = 8 * 1024 * 1024
    METRICS_TOKEN: str = ""                    # if set, /metrics requires "Authorization: Bearer <token>"
    LOG_JSON: bool = False
    LOG_LEVEL: str = "INFO"
    GENERATION_STALE_AFTER_SEC: int = 1800
    STARTUP_RECOVERY: bool = True              # mark interrupted generation jobs failed on startup

    # CORS origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000"
    ]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod", "staging")

    def production_problems(self) -> List[str]:
        """Configuration errors that must block a production start."""
        errs = []
        if len(self.AUTH_SECRET_KEY) < 32:
            errs.append("AUTH_SECRET_KEY must be set (>= 32 random characters)")
        if not self.COOKIE_SECURE:
            errs.append("COOKIE_SECURE must be true (HTTPS)")
        if not self.sync_database_url.startswith("postgresql"):
            errs.append("DATABASE_URL must point to PostgreSQL")
        if any(o.strip() == "*" or not o.startswith("https://") for o in self.CORS_ORIGINS):
            errs.append("CORS_ORIGINS must be explicit https:// origins (no wildcard)")
        if self.COOKIE_SAMESITE.lower() not in ("lax", "strict"):
            errs.append("COOKIE_SAMESITE must be lax or strict")
        return errs

    @property
    def sync_database_url(self) -> str:
        if self.DATABASE_URL:
            # Ensure using psycopg 3 driver prefix if generic postgresql:// was supplied
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
            return self.DATABASE_URL

        # Build URL from components
        user = self.POSTGRES_USER
        password = self.POSTGRES_PASSWORD
        host = self.POSTGRES_HOST
        port = self.POSTGRES_PORT
        db = self.POSTGRES_DB
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
