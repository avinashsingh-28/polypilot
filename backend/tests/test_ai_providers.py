"""Multi-provider AI: catalog, users' own encrypted keys, provider selection, and each client's wire format."""
import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from cryptography.fernet import Fernet

from app.core.config import get_settings
from app.models.user import AICredential, User
from app.services.ai import build_provider, resolve_provider
from app.services.ai.base import AIError
from app.services.ai.catalog import PROVIDERS
from tests.conftest import TEST_EMAIL, login_client

API = "/api/v1"
KEY = "sk-test-0123456789abcdefSECRET"


@pytest.fixture
def enc(monkeypatch):
    monkeypatch.setattr(get_settings(), "AI_CREDENTIALS_KEY", Fernet.generate_key().decode())


# ── catalog ──────────────────────────────────────────────────────────────────
def test_catalog_has_many_providers_with_fixed_https_endpoints():
    assert {"gemini", "anthropic", "openai", "deepseek", "groq", "mistral", "xai", "openrouter"} <= set(PROVIDERS)
    for p in PROVIDERS.values():
        assert p.key_url.startswith("https://")
        if p.kind == "openai_compat":
            assert p.base_url.startswith("https://") and not p.base_url.endswith("/")
    assert PROVIDERS["anthropic"].default_model == "claude-opus-5-5"


# ── saving keys ──────────────────────────────────────────────────────────────
def test_save_key_is_encrypted_never_returned_and_becomes_active(client, db_session, enc):
    r = client.get(f"{API}/ai/providers").json()
    assert len(r["providers"]) == len(PROVIDERS) and r["selected"] is None and r["can_save_keys"]
    saved = client.put(f"{API}/ai/providers/anthropic", json={"api_key": KEY, "model": "claude-sonnet-5-5"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["key_hint"] == "…CRET" and KEY not in saved.text
    row = db_session.query(AICredential).one()
    assert KEY not in row.api_key_encrypted and row.model == "claude-sonnet-5-5"
    overview = client.get(f"{API}/ai/providers")
    assert KEY not in overview.text and overview.json()["selected"] == "anthropic"
    st = client.get(f"{API}/ai/status").json()
    assert st["provider"] == "anthropic" and st["source"] == "own" and st["daily_limit"] == 0
    # Changing only the model keeps the key.
    client.put(f"{API}/ai/providers/anthropic", json={"model": "claude-haiku-5-5"})
    db_session.refresh(row)
    from app.services.ai.credentials import decrypt
    assert decrypt(row) == KEY and row.model == "claude-haiku-5-5"
    # A second provider does not steal the active selection.
    client.put(f"{API}/ai/providers/openai", json={"api_key": "sk-other-key-1234567"})
    assert client.get(f"{API}/ai/providers").json()["selected"] == "anthropic"


@pytest.mark.parametrize("body,code", [
    ({"api_key": "short"}, 422),
    ({"api_key": "has space in the key"}, 422),
    ({"api_key": KEY, "model": "../../etc/passwd?x=1"}, 422),
    ({"model": "gpt-5"}, 422),                          # no key saved yet
])
def test_save_key_validation(client, enc, body, code):
    assert client.put(f"{API}/ai/providers/openai", json=body).status_code == code


def test_unknown_provider_and_no_custom_urls(client, enc):
    assert client.put(f"{API}/ai/providers/evil", json={"api_key": KEY}).status_code == 404
    r = client.put(f"{API}/ai/providers/openai", json={"api_key": KEY, "base_url": "http://169.254.169.254"})
    assert r.status_code == 200 and "base_url" not in r.json()


def test_saving_refused_in_production_without_encryption_key(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "AI_CREDENTIALS_KEY", "")
    monkeypatch.setattr(s, "POLYGON_CREDENTIALS_KEY", "")
    monkeypatch.setattr(s, "ENVIRONMENT", "production")
    r = client.put(f"{API}/ai/providers/groq", json={"api_key": KEY})
    assert r.status_code == 503 and "encryption key" in r.json()["detail"]


def test_delete_and_switch_active(client, db_session, enc):
    client.put(f"{API}/ai/providers/groq", json={"api_key": KEY})
    client.put(f"{API}/ai/providers/mistral", json={"api_key": KEY})
    assert client.put(f"{API}/ai/active", json={"provider": "mistral"}).json()["provider"] == "mistral"
    assert client.put(f"{API}/ai/active", json={"provider": "xai"}).status_code == 400      # no key saved
    assert client.delete(f"{API}/ai/providers/mistral").json()["selected"] == "groq"
    assert client.delete(f"{API}/ai/providers/mistral").status_code == 404
    r = client.put(f"{API}/ai/active", json={"provider": None}).json()
    assert r["source"] in ("server", None)


def test_keys_are_private_to_each_user(client, enc):
    from fastapi.testclient import TestClient
    from app.main import app
    client.put(f"{API}/ai/providers/deepseek", json={"api_key": KEY})
    with TestClient(app) as other:
        login_client(other, "mallory@example.com", "another-strong-pass-7")
        assert all(p["saved"] is None for p in other.get(f"{API}/ai/providers").json()["providers"])
        assert other.delete(f"{API}/ai/providers/deepseek").status_code == 404
        assert other.post(f"{API}/ai/providers/deepseek/test", json={}).status_code == 404


def test_requires_login_and_csrf(client, enc):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as anon:
        assert anon.get(f"{API}/ai/providers").status_code == 401
    csrf = client.headers.pop("X-CSRF-Token", None)
    try:
        assert client.put(f"{API}/ai/providers/groq", json={"api_key": KEY}).status_code == 403
    finally:
        if csrf:
            client.headers["X-CSRF-Token"] = csrf


def test_key_test_endpoint_lists_models(client, db_session, enc):
    client.put(f"{API}/ai/providers/groq", json={"api_key": KEY, "model": "llama-3.3-70b-versatile"})

    class Fake:
        async def list_models(self):
            return ["llama-3.3-70b-versatile", "qwen-3-32b"]
    with patch("app.services.ai.credentials.provider_for", return_value=Fake()):
        ok = client.post(f"{API}/ai/providers/groq/test", json={}).json()
        missing = client.post(f"{API}/ai/providers/groq/test", json={"model": "not-there"}).json()
    assert ok["ok"] and ok["model_available"] and ok["saved"]["last_test_ok"] is True
    assert missing["model_available"] is False and missing["saved"]["last_test_ok"] is False

    class Bad:
        async def list_models(self):
            raise AIError("auth", "Groq rejected the API key")
    with patch("app.services.ai.credentials.provider_for", return_value=Bad()):
        bad = client.post(f"{API}/ai/providers/groq/test", json={}).json()
    assert bad["ok"] is False and "rejected" in bad["error"] and KEY not in json.dumps(bad)


# ── selection ────────────────────────────────────────────────────────────────
def test_resolve_prefers_users_own_key(client, db_session, enc, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(s, "GEMINI_API_KEY", "")
    user = db_session.query(User).filter_by(email=TEST_EMAIL).one()
    with pytest.raises(AIError) as e:
        resolve_provider(db_session, user.id, s)
    assert e.value.kind == "missing_key" and "AI Providers page" in e.value.message
    client.put(f"{API}/ai/providers/openai", json={"api_key": KEY, "model": "gpt-5"})
    db_session.expire_all()
    prov, limit = resolve_provider(db_session, user.id, s)
    assert prov.name == "openai" and prov.model == "gpt-5" and limit == 0


def test_generation_runs_on_own_key_without_server_key(client, db_session, enc, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "GEMINI_API_KEY", "")
    monkeypatch.setattr(s, "AI_PROVIDER", "gemini")
    pid = client.post(f"{API}/problems", json={"title": "Own key", "idea": "sum"}).json()["id"]
    assert client.post(f"{API}/problems/{pid}/generate").status_code == 503
    client.put(f"{API}/ai/providers/anthropic", json={"api_key": KEY})
    with patch("app.api.routes.generation.run_generation_pipeline", new_callable=AsyncMock):
        assert client.post(f"{API}/problems/{pid}/generate").status_code == 202


# ── OpenAI-compatible wire format ────────────────────────────────────────────
def _compat(provider, handler, model="m-1"):
    return build_provider(provider, KEY, model, get_settings(), transport=httpx.MockTransport(handler))


def test_openai_request_shape_and_json_mode():
    seen = {}

    def handler(req):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": 'Sure: {"a": 1} done'}}]})
    out = asyncio.run(_compat("openai", handler, "gpt-5").generate_json("give json"))
    assert out == {"a": 1}
    assert seen["url"] == "https://api.openai.com/v1/chat/completions" and seen["auth"] == f"Bearer {KEY}"
    b = seen["body"]
    assert b["model"] == "gpt-5" and "temperature" not in b and b["max_completion_tokens"] >= 32000
    assert b["response_format"] == {"type": "json_object"}


def test_groq_sends_temperature_and_max_tokens():
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})
    assert asyncio.run(_compat("groq", handler).generate_text("hi", temperature=0.3)) == "hello"
    assert seen["temperature"] == 0.3 and "max_tokens" in seen and "response_format" not in seen


@pytest.mark.parametrize("status,kind", [(401, "auth"), (404, "model_not_found"), (400, "invalid_request")])
def test_openai_errors_are_normalized_and_scrubbed(status, kind):
    def handler(req):
        return httpx.Response(status, json={"error": {"message": f"Bad request for key {KEY}"}})
    with pytest.raises(AIError) as e:
        asyncio.run(_compat("openai", handler).generate_text("x"))
    assert e.value.kind == kind and KEY not in e.value.message


def test_transient_errors_are_retried(monkeypatch):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(429 if len(calls) == 1 else 200, json={"choices": [{"message": {"content": "ok"}}]})
    monkeypatch.setattr("app.services.ai.openai_compat.asyncio.sleep", AsyncMock())
    assert asyncio.run(_compat("deepseek", handler).generate_text("x")) == "ok" and len(calls) == 2


def test_list_models_compat():
    def handler(req):
        assert req.url.path.endswith("/models")
        return httpx.Response(200, json={"data": [{"id": "b"}, {"id": "a"}, {"id": "a"}]})
    assert asyncio.run(_compat("together", handler).list_models()) == ["a", "b"]


# ── Anthropic (official SDK, mocked transport) ───────────────────────────────
def _sse(text, stop_reason="end_turn"):
    events = [
        ("message_start", {"type": "message_start", "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5", "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 5, "output_tokens": 0}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0,
                                 "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                 "delta": {"type": "text_delta", "text": text}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                           "usage": {"output_tokens": 3}}),
        ("message_stop", {"type": "message_stop"}),
    ]
    return "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in events)


def _claude(model, handler):
    import httpx2
    from app.services.ai.anthropic_provider import AnthropicProvider
    return AnthropicProvider(KEY, model, max_retries=0,
                             http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))


def _sse_handler(seen, text='{"ok": true}', stop_reason="end_turn"):
    import httpx2

    def handler(req):
        seen["path"], seen["headers"], seen["body"] = req.url.path, dict(req.headers), json.loads(req.content)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"},
                               content=_sse(text, stop_reason).encode())
    return handler


def test_claude_opus_request_uses_effort_and_fallbacks_without_temperature():
    seen = {}
    out = asyncio.run(_claude("claude-opus-5-5", _sse_handler(seen)).generate_json("make json", temperature=0.7))
    assert out == {"ok": True}
    b, h = seen["body"], seen["headers"]
    assert seen["path"] == "/v1/messages" and b["model"] == "claude-opus-5-5" and b["stream"] is True
    assert "temperature" not in b and b["max_tokens"] >= 32000
    assert b["output_config"] == {"effort": "high"} and b["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in h.get("anthropic-beta", "")
    assert KEY in (h.get("x-api-key", "") + h.get("authorization", ""))      # the user's key, not ambient credentials


def test_claude_haiku_has_no_fallback_beta():
    seen = {}
    assert asyncio.run(_claude("claude-haiku-5-5", _sse_handler(seen, "hi")).generate_text("x")) == "hi"
    assert "fallbacks" not in seen["body"] and "anthropic-beta" not in seen["headers"]


def test_claude_refusal_and_auth_errors():
    seen = {}
    with pytest.raises(AIError) as e:
        asyncio.run(_claude("claude-opus-5-5", _sse_handler(seen, "", "refusal")).generate_text("x"))
    assert e.value.kind == "refused"
    import httpx2

    def unauthorized(req):
        return httpx2.Response(401, json={"type": "error", "error": {"type": "authentication_error",
                                                                     "message": "invalid x-api-key"}})
    with pytest.raises(AIError) as e:
        asyncio.run(_claude("claude-opus-5-5", unauthorized).generate_text("x"))
    assert e.value.kind == "auth" and KEY not in e.value.message


def test_claude_list_models():
    import httpx2

    def handler(req):
        assert req.url.path == "/v1/models"
        return httpx2.Response(200, json={"data": [{"type": "model", "id": "claude-opus-5-5", "display_name": "Opus",
                                                    "created_at": "2026-01-01T00:00:00Z"}],
                                          "has_more": False, "first_id": "claude-opus-5-5",
                                          "last_id": "claude-opus-5-5"})
    assert asyncio.run(_claude("claude-opus-5-5", handler).list_models()) == ["claude-opus-5-5"]


def test_openrouter_test_verifies_key_and_xai_400_is_auth():
    def openrouter(req):
        if req.url.path.endswith("/key"):
            return httpx.Response(401, json={"error": {"message": "No auth credentials found"}})
        return httpx.Response(200, json={"data": [{"id": "public/model"}]})
    with pytest.raises(AIError) as e:
        asyncio.run(_compat("openrouter", openrouter).list_models())
    assert e.value.kind == "auth"

    def xai(req):
        return httpx.Response(400, json={"error": "Incorrect API key provided."})
    with pytest.raises(AIError) as e:
        asyncio.run(_compat("xai", xai).list_models())
    assert e.value.kind == "auth"
