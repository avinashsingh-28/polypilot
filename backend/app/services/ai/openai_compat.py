"""
OpenAI and OpenAI-compatible providers (OpenAI, DeepSeek, Groq, Mistral, xAI, OpenRouter,
Together, Fireworks, Cerebras) over the Chat Completions API.

Base URLs come only from the server-side catalog. Transient failures (429 / 5xx / timeouts /
network) are retried with backoff; the API key never appears in errors or logs.
"""
import asyncio
import logging
import random
from typing import Optional

import httpx

from app.services.ai.base import AIError, AIProvider, JSONRetryMixin, scrub
from app.services.ai.catalog import ProviderSpec

logger = logging.getLogger(__name__)


class OpenAICompatProvider(JSONRetryMixin, AIProvider):
    def __init__(self, spec: ProviderSpec, api_key: str, model: str, *, timeout_sec: float = 120.0,
                 max_retries: int = 2, max_output_tokens: int = 8192, max_prompt_chars: int = 60000,
                 transport: Optional[httpx.AsyncBaseTransport] = None):
        if not api_key:
            raise AIError("missing_key", f"No {spec.label} API key configured")
        self.spec, self.name, self.model = spec, spec.id, model
        self._key = api_key
        self.timeout_sec, self.max_retries = timeout_sec, max_retries
        self.max_output_tokens = max(max_output_tokens, spec.min_output_tokens)
        self.max_prompt_chars = max_prompt_chars
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        if self.spec.id == "openrouter":
            headers["X-Title"] = "PolyPilot"
        return httpx.AsyncClient(base_url=self.spec.base_url, headers=headers, timeout=self.timeout_sec,
                                 transport=self._transport, follow_redirects=False)

    def _error(self, r: httpx.Response) -> AIError:
        try:
            body = r.json()
            detail = body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else body.get("error")
            detail = detail or body.get("message") or ""
        except ValueError:
            detail = ""
        detail = scrub(str(detail), self._key)
        label, code = self.spec.label, r.status_code
        if code in (401, 403) or (code == 400 and "api key" in detail.lower()):
            return AIError("auth", f"{label} rejected the API key")
        if code == 404:
            return AIError("model_not_found", f"{label}: model {self.model!r} not found or not available for this key")
        if code == 429:
            return AIError("rate_limited", f"{label} rate limit or quota exceeded" + (f": {detail}" if detail else ""))
        if code >= 500:
            return AIError("unavailable", f"{label} is overloaded or unavailable (HTTP {code})")
        if code == 400 and "model" in detail.lower():
            return AIError("model_not_found", f"{label}: {detail}")
        return AIError("invalid_request", f"{label} rejected the request ({code})" + (f": {detail}" if detail else ""))

    async def _generate(self, prompt: str, temperature: float, json_mode: bool) -> str:
        if len(prompt) > self.max_prompt_chars:
            raise AIError("prompt_too_large", f"Prompt exceeds {self.max_prompt_chars} characters")
        body = {"model": self.model, "messages": [{"role": "user", "content": prompt}],
                self.spec.max_tokens_param: self.max_output_tokens}
        if self.spec.send_temperature:
            body["temperature"] = temperature
        if json_mode and self.spec.json_mode:
            body["response_format"] = {"type": "json_object"}
        last: Optional[AIError] = None
        async with self._client() as client:
            for attempt in range(1 + self.max_retries):
                try:
                    r = await client.post("/chat/completions", json=body)
                    if r.status_code != 200:
                        raise self._error(r)
                    data = r.json()
                    choice = (data.get("choices") or [{}])[0]
                    text = (choice.get("message") or {}).get("content") or ""
                    if isinstance(text, list):      # some providers return content parts
                        text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
                    if not text.strip():
                        if choice.get("finish_reason") == "length":
                            raise AIError("invalid_response", f"{self.spec.label} ran out of output tokens before answering")
                        raise AIError("invalid_response", f"{self.spec.label} returned an empty response")
                    return text
                except AIError as e:
                    last = e
                except httpx.TimeoutException:
                    last = AIError("timeout", f"{self.spec.label} request timed out")
                except (httpx.HTTPError, ValueError):
                    last = AIError("unavailable", f"{self.spec.label} unreachable or returned invalid data")
                if not last.transient or attempt == self.max_retries:
                    logger.warning("ai call failed", extra={"provider": self.spec.id, "kind": last.kind})
                    raise last
                await asyncio.sleep(min(20.0, 2 ** attempt * 2) + random.random())
        raise last  # pragma: no cover

    async def list_models(self) -> list[str]:
        async with self._client() as client:
            try:
                if self.spec.key_check_path:          # model list is public here; verify the key first
                    k = await client.get(self.spec.key_check_path)
                    if k.status_code != 200:
                        raise self._error(k)
                r = await client.get("/models")
            except httpx.TimeoutException:
                raise AIError("timeout", f"{self.spec.label} request timed out")
            except httpx.HTTPError:
                raise AIError("unavailable", f"{self.spec.label} unreachable")
            if r.status_code != 200:
                raise self._error(r)
            try:
                items = r.json().get("data") or []
            except ValueError:
                raise AIError("invalid_response", f"{self.spec.label} returned an invalid model list")
            return sorted({str(m.get("id")) for m in items if isinstance(m, dict) and m.get("id")})
