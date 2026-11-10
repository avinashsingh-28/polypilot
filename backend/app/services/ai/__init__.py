"""Package init — exposes get_ai_provider factory."""
from app.services.ai.base import AIProvider


def get_ai_provider(settings) -> AIProvider:
    """Return configured AI provider based on settings."""
    provider = getattr(settings, "AI_PROVIDER", "gemini").lower()
    if provider == "gemini":
        from app.services.ai.gemini import GeminiProvider
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=getattr(settings, "AI_MODEL", "gemini-1.5-flash"),
        )
    raise ValueError(f"Unknown AI_PROVIDER: {provider!r}")

