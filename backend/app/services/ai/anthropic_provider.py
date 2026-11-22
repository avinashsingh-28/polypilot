"""
Anthropic Claude provider (official `anthropic` SDK, async + streaming).

- Streams every request and reads the final message, so long outputs never hit HTTP timeouts.
- No `temperature`: current Claude models reject sampling parameters.
- Effort "high" on models that support it (code generation benefits from deeper reasoning).
- Server-side refusal fallbacks are enabled on the models that support them; a refusal that the
  whole chain declines is reported as AIError('refused').
- The SDK retries 408/409/429/5xx and connection errors itself (max_retries).
"""
import logging
from typing import Any

from app.services.ai.base import AIError, AIProvider, JSONRetryMixin, scrub

logger = logging.getLogger(__name__)

EFFORT_PREFIXES = ("claude-opus-5", "claude-sonnet-5", "claude-haiku-5", "claude-fable-5", "claude-mythos-5",
                   "claude-opus-4-5", "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8", "claude-sonnet-4-6")
FALLBACK_MODELS = {"claude-fable-5-2", "claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 32000          # includes adaptive thinking; streamed, so no timeout concern


class AnthropicProvider(JSONRetryMixin, AIProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-opus-5-5", *, timeout_sec: float = 300.0,
                 max_retries: int = 2, max_output_tokens: int = MAX_TOKENS, max_prompt_chars: int = 60000,
                 http_client=None):
        if not api_key:
            raise AIError("missing_key", "No Anthropic API key configured")
        try:
            import anthropic
        except ImportError:  # pragma: no cover
            raise AIError("unavailable", "The anthropic package is not installed")
        self._sdk = anthropic
        self._key = api_key
        # The key is always passed explicitly, so no ambient credentials (env vars, CLI profiles) are used.
        kw = {"http_client": http_client} if http_client is not None else {}
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=max(timeout_sec, 300.0),
                                                max_retries=max_retries, **kw)
        self.model = model
        self.max_output_tokens = max(max_output_tokens, MAX_TOKENS)
        self.max_prompt_chars = max_prompt_chars

    def _classify(self, exc: Exception) -> AIError:
        a = self._sdk
        if isinstance(exc, AIError):
            return exc
        if isinstance(exc, a.AuthenticationError):
            return AIError("auth", "Anthropic rejected the API key")
        if isinstance(exc, a.PermissionDeniedError):
            return AIError("auth", "This Anthropic API key is not allowed to use this model")
        if isinstance(exc, a.NotFoundError):
            return AIError("model_not_found", f"Claude model {self.model!r} was not found. Pick another model.")
        if isinstance(exc, a.RateLimitError):
            return AIError("rate_limited", "Anthropic rate limit reached. Try again shortly.")
        if isinstance(exc, a.APITimeoutError):
            return AIError("timeout", "Anthropic request timed out")
        if isinstance(exc, a.APIConnectionError):
            return AIError("unavailable", "Anthropic API unreachable")
        if isinstance(exc, a.APIStatusError):
            if exc.status_code >= 500:
                return AIError("unavailable", f"Anthropic is overloaded or unavailable (HTTP {exc.status_code})")
            return AIError("invalid_request", f"Anthropic rejected the request: {scrub(exc.message, self._key)}")
        return AIError("unavailable", f"Anthropic error ({type(exc).__name__})")

    def _params(self, prompt: str, json_mode: bool) -> dict:
        params: dict[str, Any] = {"model": self.model, "max_tokens": self.max_output_tokens,
                                  "messages": [{"role": "user", "content": prompt}]}
        if json_mode:
            params["system"] = "You output only valid JSON when asked for JSON."
        if self.model.startswith(EFFORT_PREFIXES):
            params["output_config"] = {"effort": "high"}
        return params

    async def _generate(self, prompt: str, temperature: float, json_mode: bool) -> str:
        if len(prompt) > self.max_prompt_chars:
            raise AIError("prompt_too_large", f"Prompt exceeds {self.max_prompt_chars} characters")
        params = self._params(prompt, json_mode)
        try:
            if self.model in FALLBACK_MODELS:
                stream = self._client.beta.messages.stream(**params, betas=[FALLBACK_BETA], fallbacks="default")
            else:
                stream = self._client.messages.stream(**params)
            async with stream as s:
                msg = await s.get_final_message()
        except Exception as exc:  # noqa: BLE001 - normalized below
            err = self._classify(exc)
            logger.warning("ai call failed", extra={"provider": "anthropic", "kind": err.kind})
            raise err
        if msg.stop_reason == "refusal":
            raise AIError("refused", "Claude declined this request.")
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        if msg.stop_reason == "max_tokens" and not text.strip():
            raise AIError("invalid_response", "Claude ran out of output tokens before answering")
        if not text.strip():
            raise AIError("invalid_response", "Claude returned an empty response")
        return text

    async def list_models(self) -> list[str]:
        try:
            ids = [m.id async for m in self._client.models.list(limit=100)]
        except Exception as exc:  # noqa: BLE001
            raise self._classify(exc)
        return ids
