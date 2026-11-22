"""AI provider factory + usage tracking.

Providers and their endpoints come from a server-side catalog; users may save their own API key
for any of them, but never a URL (no SSRF surface).
"""
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import func

from app.services.ai.base import AIError, AIProvider

from app.services.ai.catalog import PROVIDERS, get_spec

SUPPORTED_PROVIDERS = tuple(PROVIDERS)


def build_provider(provider_id: str, api_key: str, model: str, settings, *, transport=None) -> AIProvider:
    """Construct a provider from the server-side catalog (never from a user-supplied URL)."""
    spec = get_spec(provider_id)
    if spec is None:
        raise AIError("invalid_request", f"Unsupported AI provider {provider_id!r}; supported: {', '.join(PROVIDERS)}")
    common = dict(timeout_sec=settings.AI_TIMEOUT_SEC, max_retries=settings.AI_MAX_RETRIES,
                  max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS, max_prompt_chars=settings.AI_MAX_PROMPT_CHARS)
    model = model or spec.default_model
    if spec.kind == "gemini":
        from app.services.ai.gemini import GeminiProvider
        return GeminiProvider(api_key=api_key, model=model, **common)
    if spec.kind == "anthropic":
        from app.services.ai.anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=api_key, model=model, **common)
    from app.services.ai.openai_compat import OpenAICompatProvider
    return OpenAICompatProvider(spec, api_key, model, transport=transport, **common)


def server_key(settings) -> str:
    provider = (getattr(settings, "AI_PROVIDER", "gemini") or "gemini").lower()
    return settings.GEMINI_API_KEY if provider == "gemini" else getattr(settings, "AI_API_KEY", "")


def get_ai_provider(settings) -> AIProvider:
    """The server's own provider (AI_PROVIDER + its key in backend/.env)."""
    provider = (getattr(settings, "AI_PROVIDER", "gemini") or "gemini").lower()
    key = server_key(settings)
    if not key:
        raise AIError("missing_key", "No AI provider configured. Add your own API key on the AI Providers page.")
    return build_provider(provider, key, getattr(settings, "AI_MODEL", ""), settings)


def ai_available(db, user_id, settings) -> bool:
    """True if this user's AI calls have a provider: their selected own key, or the server's key."""
    from app.models.user import AICredential, User
    user = db.get(User, user_id) if user_id is not None else None
    if user is not None and user.ai_provider and db.query(AICredential.id).filter_by(
            user_id=user.id, provider=user.ai_provider).first() is not None:
        return True
    return bool(server_key(settings)) and get_spec(str(getattr(settings, "AI_PROVIDER", "") or "")) is not None


NO_AI = "No AI provider is set up. Add your own API key on the AI Providers page (Gemini, Claude, OpenAI, …)."


def resolve_provider(db, user_id, settings) -> tuple[AIProvider, int]:
    """Provider for a user's AI calls, and the daily call limit that applies.

    1. The provider the user selected, with their own saved key (no server limit: their quota).
    2. Otherwise the server's provider, with the per-user daily limit.
    """
    from app.services.ai.credentials import load_user_provider
    if user_id is not None:
        own = load_user_provider(db, user_id, settings)
        if own is not None:
            return own, 0
    return get_ai_provider(settings), settings.AI_MAX_CALLS_PER_USER_PER_DAY


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
