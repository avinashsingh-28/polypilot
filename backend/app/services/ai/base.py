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


def strip_fences(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])
    return raw.strip()


def loads_lenient(raw: str) -> Any:
    """json.loads after removing code fences and any prose around the outermost object/array."""
    import json
    text = strip_fences(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
        if not starts:
            raise
        start = min(starts)
        end = text.rfind("}" if text[start] == "{" else "]")
        if end <= start:
            raise
        return json.loads(text[start:end + 1])


JSON_INSTRUCTION = ("\n\nRespond with ONLY a single valid JSON value. No prose before or after it, "
                    "no markdown code fences.")


class JSONRetryMixin:
    """generate_json for providers that implement `_generate(prompt, temperature, json_mode)`:
    parses leniently and, if the output is malformed, asks the model once to repair it."""
    max_prompt_chars = 60000

    async def generate_json(self, prompt: str, *, temperature: float = 0.2) -> Any:
        import json
        raw = await self._generate(prompt + JSON_INSTRUCTION, temperature, True)
        try:
            return loads_lenient(raw)
        except (json.JSONDecodeError, ValueError):
            pass
        fixed = await self._generate(
            "The following text is not valid JSON. Return ONLY the corrected JSON:\n\n"
            + raw[:self.max_prompt_chars - 200], 0.0, True)
        try:
            return loads_lenient(fixed)
        except (json.JSONDecodeError, ValueError):
            raise AIError("invalid_response", "AI provider returned malformed JSON")

    async def generate_text(self, prompt: str, *, temperature: float = 0.4) -> str:
        return await self._generate(prompt, temperature, False)


def scrub(message: str, secret: str) -> str:
    """Remove a secret (and long fragments of it) from a provider error message."""
    msg = str(message or "")[:300]
    if secret:
        msg = msg.replace(secret, "[redacted]")
        if len(secret) > 12:
            msg = msg.replace(secret[:12], "[redacted]").replace(secret[-8:], "[redacted]")
    return msg
