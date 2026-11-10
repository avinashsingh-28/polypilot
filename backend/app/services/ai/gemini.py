"""
Gemini AI provider implementation using the google-genai SDK.
"""
import json
import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """AI provider backed by Google Gemini (google-genai SDK)."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        try:
            from google import genai
            self._client = genai.Client(api_key=api_key)
        except ImportError:
            raise RuntimeError(
                "google-genai is not installed. Run: pip install google-genai"
            )
        self._model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def generate_text(self, prompt: str, *, temperature: float = 0.4) -> str:
        """Call Gemini and return plain text."""
        from google.genai import types as genai_types

        config = genai_types.GenerateContentConfig(temperature=temperature)
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        return response.text or ""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def generate_json(self, prompt: str, *, temperature: float = 0.2) -> Any:
        """Call Gemini expecting JSON output; parse and return the Python object."""
        from google.genai import types as genai_types

        config = genai_types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        raw = (response.text or "").strip()

        # Strip markdown code fences if the model wrapped the JSON
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse failed on first attempt, retrying: %s", exc)
            # Ask the model to fix it
            fix_prompt = (
                f"The following text is not valid JSON. Fix it and return ONLY the corrected JSON:\n\n{raw}"
            )
            fix_config = genai_types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            )
            fix_response = self._client.models.generate_content(
                model=self._model,
                contents=fix_prompt,
                config=fix_config,
            )
            return json.loads((fix_response.text or "").strip())

