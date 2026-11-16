"""
Gemini AI provider (google-genai SDK).

Hardening: async client (does not block the event loop), hard per-call timeout, output-token cap,
prompt-size cap, retries only for transient failures (429 / 5xx / timeouts / network), normalized
AIError kinds, and safe JSON parsing (a malformed response is retried once by asking the model to
fix it; anything else raises AIError('invalid_response')).
"""
import asyncio
import json
import logging
import random
from typing import Any, Optional

from app.services.ai.base import AIError, AIProvider

logger = logging.getLogger(__name__)


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])
    return raw


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-3.5-flash", *, timeout_sec: float = 120.0,
                 max_retries: int = 2, max_output_tokens: int = 8192, max_prompt_chars: int = 60000):
        if not api_key:
            raise AIError("missing_key", "GEMINI_API_KEY is not configured")
        try:
            from google import genai
            from google.genai import types
        except ImportError:  # pragma: no cover
            raise AIError("unavailable", "google-genai is not installed")
        self._types = types
        self._client = genai.Client(api_key=api_key,
                                    http_options=types.HttpOptions(timeout=int(timeout_sec * 1000)))
        self.model = model
        self.timeout_sec, self.max_retries = timeout_sec, max_retries
        self.max_output_tokens, self.max_prompt_chars = max_output_tokens, max_prompt_chars

    @staticmethod
    def _classify(exc: Exception) -> AIError:
        if isinstance(exc, AIError):
            return exc
        if isinstance(exc, asyncio.TimeoutError):
            return AIError("timeout", "AI provider timed out")
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        name = type(exc).__name__
        if code == 429:
            return AIError("rate_limited", "AI provider rate limit or quota exceeded")
        if code in (401, 403):
            return AIError("auth", "AI provider rejected the API key")
        if code == 404:
            # Google's message names the recommended replacement model; it contains no secrets.
            detail = str(getattr(exc, "message", "") or "").split(" We recommend")[0][:240]
            return AIError("model_not_found", "AI model not found or not available for this API key — set AI_MODEL "
                                              "in backend/.env to a current model." + (f" Provider says: {detail}" if detail else ""))
        if isinstance(code, int) and code >= 500:
            return AIError("unavailable", f"AI provider is overloaded or temporarily unavailable (HTTP {code}). "
                                          "Try again in a few minutes, or set AI_MODEL to another model.")
        if isinstance(code, int) and 400 <= code < 500:
            return AIError("invalid_request", f"AI provider rejected the request ({code})")
        if "Timeout" in name or "Connect" in name or "Network" in name or isinstance(exc, (ConnectionError, OSError)):
            return AIError("unavailable", "AI provider unreachable")
        return AIError("unavailable", f"AI provider error ({name})")

    async def _generate(self, prompt: str, temperature: float, json_mode: bool) -> str:
        if len(prompt) > self.max_prompt_chars:
            raise AIError("prompt_too_large", f"Prompt exceeds {self.max_prompt_chars} characters")
        cfg = self._types.GenerateContentConfig(
            temperature=temperature, max_output_tokens=self.max_output_tokens,
            **({"response_mime_type": "application/json"} if json_mode else {}))
        last: Optional[AIError] = None
        for attempt in range(1 + self.max_retries):
            try:
                resp = await asyncio.wait_for(
                    self._client.aio.models.generate_content(model=self.model, contents=prompt, config=cfg),
                    timeout=self.timeout_sec)
                text = getattr(resp, "text", None) or ""
                if not text.strip():
                    raise AIError("invalid_response", "AI provider returned an empty response")
                return text
            except Exception as exc:  # noqa: BLE001 - normalized below
                last = self._classify(exc)
                if not last.transient or attempt == self.max_retries:
                    logger.warning("ai call failed", extra={"provider": "gemini", "kind": last.kind})
                    raise last
                await asyncio.sleep(min(20.0, 2 ** attempt * 2) + random.random())
        raise last  # pragma: no cover

    async def generate_text(self, prompt: str, *, temperature: float = 0.4) -> str:
        return await self._generate(prompt, temperature, json_mode=False)

    async def generate_json(self, prompt: str, *, temperature: float = 0.2) -> Any:
        raw = _strip_fences(await self._generate(prompt, temperature, json_mode=True))
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("ai returned malformed JSON; asking once for a fix")
        fixed = _strip_fences(await self._generate(
            "The following text is not valid JSON. Return ONLY the corrected JSON:\n\n" + raw[:self.max_prompt_chars - 200],
            0.0, json_mode=True))
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            raise AIError("invalid_response", "AI provider returned malformed JSON")
