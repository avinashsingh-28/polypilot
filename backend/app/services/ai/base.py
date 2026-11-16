from abc import ABC, abstractmethod
from typing import Any


class AIError(Exception):
    """Normalized AI provider failure.
    kinds: missing_key, auth, rate_limited, timeout, unavailable, invalid_request,
           invalid_response, prompt_too_large, quota_exceeded (local per-user limit)"""
    TRANSIENT = {"rate_limited", "timeout", "unavailable"}

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind, self.message = kind, message

    @property
    def transient(self) -> bool:
        return self.kind in self.TRANSIENT


class AIProvider(ABC):
    """Abstract base class for AI providers."""
    name = "unknown"
    model = "unknown"

    @abstractmethod
    async def generate_text(self, prompt: str, *, temperature: float = 0.4) -> str:
        """Generate a plain-text response from the given prompt."""

    @abstractmethod
    async def generate_json(self, prompt: str, *, temperature: float = 0.2) -> Any:
        """Generate a JSON-parseable response and return the parsed object."""
