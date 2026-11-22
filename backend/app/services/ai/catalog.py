"""
Catalog of supported AI providers.

Every endpoint is fixed here on the server. Users can only choose a provider id, a model name and
their own API key; they can never supply a URL (no SSRF surface).
Default models are suggestions; "Test key" lists the models the user's key can actually use.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

MODEL_RE = re.compile(r"^[A-Za-z0-9._:/@+\-]{1,120}$")


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    kind: str                      # gemini | anthropic | openai_compat
    default_model: str
    key_url: str                   # where users create a key
    key_prefix_hint: str = ""      # shown as input placeholder only
    base_url: str = ""             # openai_compat only
    json_mode: bool = False        # supports response_format={"type": "json_object"}
    send_temperature: bool = True
    max_tokens_param: str = "max_tokens"
    min_output_tokens: int = 0     # reasoning models spend output budget on thinking
    key_check_path: str = ""       # authenticated endpoint to verify a key when /models is public
    suggested_models: tuple = field(default_factory=tuple)
    description: str = ""


PROVIDERS: dict[str, ProviderSpec] = {p.id: p for p in [
    ProviderSpec("gemini", "Google Gemini", "gemini", "gemini-3.5-flash", "https://aistudio.google.com/apikey",
                 "AIza…", suggested_models=("gemini-3.5-flash",),
                 description="Google's Gemini models (AI Studio key)."),
    ProviderSpec("anthropic", "Anthropic Claude", "anthropic", "claude-opus-5-5",
                 "https://console.anthropic.com/settings/keys", "sk-ant-…",
                 suggested_models=("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-2"),
                 description="Claude models via the official Anthropic SDK."),
    ProviderSpec("openai", "OpenAI", "openai_compat", "gpt-5", "https://platform.openai.com/api-keys", "sk-…",
                 base_url="https://api.openai.com/v1", json_mode=True, send_temperature=False,
                 max_tokens_param="max_completion_tokens", min_output_tokens=32000,
                 description="GPT models (Chat Completions API)."),
    ProviderSpec("deepseek", "DeepSeek", "openai_compat", "deepseek-chat", "https://platform.deepseek.com/api_keys",
                 "sk-…", base_url="https://api.deepseek.com/v1", json_mode=True,
                 description="DeepSeek chat and reasoning models."),
    ProviderSpec("groq", "Groq", "openai_compat", "llama-3.3-70b-versatile", "https://console.groq.com/keys", "gsk_…",
                 base_url="https://api.groq.com/openai/v1", json_mode=True,
                 description="Very fast open models (Llama, Qwen, GPT-OSS…)."),
    ProviderSpec("mistral", "Mistral AI", "openai_compat", "mistral-large-latest", "https://console.mistral.ai/api-keys",
                 base_url="https://api.mistral.ai/v1", json_mode=True,
                 description="Mistral and Codestral models."),
    ProviderSpec("xai", "xAI Grok", "openai_compat", "grok-4", "https://console.x.ai", "xai-…",
                 base_url="https://api.x.ai/v1", json_mode=True, description="Grok models."),
    ProviderSpec("openrouter", "OpenRouter", "openai_compat", "openrouter/auto", "https://openrouter.ai/keys", "sk-or-…",
                 base_url="https://openrouter.ai/api/v1", key_check_path="/key",
                 description="One key for hundreds of models from many providers."),
    ProviderSpec("together", "Together AI", "openai_compat", "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                 "https://api.together.ai/settings/api-keys", base_url="https://api.together.xyz/v1",
                 description="Open-source models (Llama, Qwen, DeepSeek…)."),
    ProviderSpec("fireworks", "Fireworks AI", "openai_compat", "accounts/fireworks/models/llama-v3p3-70b-instruct",
                 "https://fireworks.ai/account/api-keys", "fw_…", base_url="https://api.fireworks.ai/inference/v1",
                 description="Fast inference for open models."),
    ProviderSpec("cerebras", "Cerebras", "openai_compat", "llama-3.3-70b", "https://cloud.cerebras.ai", "csk-…",
                 base_url="https://api.cerebras.ai/v1", description="Ultra-fast inference for open models."),
]}


def get_spec(provider_id: str) -> Optional[ProviderSpec]:
    return PROVIDERS.get((provider_id or "").lower())


def valid_model(model: str) -> bool:
    return bool(MODEL_RE.match(model or ""))
