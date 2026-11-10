from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    async def generate_text(self, prompt: str, *, temperature: float = 0.4) -> str:
        """Generate a plain-text response from the given prompt."""

    @abstractmethod
    async def generate_json(self, prompt: str, *, temperature: float = 0.2) -> Any:
        """Generate a JSON-parseable response and return the parsed object."""

