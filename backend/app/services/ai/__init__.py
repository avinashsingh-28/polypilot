"""AI provider factory + usage tracking.

Only server-configured providers are supported (no user-supplied base URLs → no SSRF surface).
"""
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import func

from app.services.ai.base import AIError, AIProvider

SUPPORTED_PROVIDERS = ("gemini",)


def get_ai_provider(settings) -> AIProvider:
    """Return configured AI provider based on settings."""
    provider = getattr(settings, "AI_PROVIDER", "gemini").lower()
    if provider == "gemini":
        from app.services.ai.gemini import GeminiProvider
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=getattr(settings, "AI_MODEL", "gemini-1.5-flash"),
            timeout_sec=settings.AI_TIMEOUT_SEC, max_retries=settings.AI_MAX_RETRIES,
            max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS, max_prompt_chars=settings.AI_MAX_PROMPT_CHARS,
        )
    raise AIError("invalid_request", f"Unsupported AI_PROVIDER {provider!r}; supported: {SUPPORTED_PROVIDERS}")


def calls_today(db, user_id) -> int:
    from app.models.user import AIUsage
    since = datetime.now(timezone.utc) - timedelta(days=1)
    return db.query(func.count(AIUsage.id)).filter(AIUsage.user_id == user_id, AIUsage.created_at >= since).scalar() or 0


class TrackedProvider(AIProvider):
    """Wraps a provider: enforces the per-user daily call limit and records size/outcome of each
    call (never prompt or response content)."""

    def __init__(self, inner: AIProvider, session_factory: Callable[[], Any], user_id: Optional[uuid.UUID],
                 problem_id: Optional[uuid.UUID], purpose: str, daily_limit: int):
        self.inner, self.session_factory = inner, session_factory
        self.user_id, self.problem_id, self.purpose, self.daily_limit = user_id, problem_id, purpose, daily_limit
        self.name, self.model = getattr(inner, "name", "unknown"), getattr(inner, "model", "unknown")

    def _session(self):
        s = self.session_factory()
        return s if hasattr(s, "__enter__") else _Borrowed(s)

    def _check_quota(self):
        if self.user_id is None or self.daily_limit <= 0:
            return
        with self._session() as db:
            if calls_today(db, self.user_id) >= self.daily_limit:
                raise AIError("quota_exceeded", f"Daily AI call limit ({self.daily_limit}) reached for this account")

    def _record(self, prompt: str, result: Any, err: Optional[AIError], started: float):
        from app.models.user import AIUsage
        size = len(result) if isinstance(result, str) else len(str(result)) if result is not None else 0
        with self._session() as db:
            db.add(AIUsage(user_id=self.user_id, problem_id=self.problem_id, purpose=self.purpose[:50],
                           provider=self.name[:30], model=str(self.model)[:80], prompt_chars=len(prompt),
                           response_chars=size, status="ok" if err is None else "error",
                           error_kind=err.kind if err else None, duration_ms=int((time.monotonic() - started) * 1000)))
            db.commit()

    async def _call(self, fn, prompt, **kw):
        self._check_quota()
        started = time.monotonic()
        try:
            result = await fn(prompt, **kw)
        except AIError as e:
            self._record(prompt, None, e, started)
            raise
        except Exception as exc:
            e = AIError("unavailable", f"AI provider error ({type(exc).__name__})")
            self._record(prompt, None, e, started)
            raise e from exc
        self._record(prompt, result, None, started)
        return result

    async def generate_text(self, prompt: str, *, temperature: float = 0.4) -> str:
        return await self._call(self.inner.generate_text, prompt, temperature=temperature)

    async def generate_json(self, prompt: str, *, temperature: float = 0.2) -> Any:
        return await self._call(self.inner.generate_json, prompt, temperature=temperature)


class _Borrowed:
    """Context wrapper for an existing session (not closed on exit)."""

    def __init__(self, s):
        self.s = s

    def __enter__(self):
        return self.s

    def __exit__(self, *a):
        return False
