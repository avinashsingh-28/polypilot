"""
AI providers for the current user. API keys can be saved (encrypted) but are never returned.

GET    /ai/status                    the provider this user's AI calls will use right now
GET    /ai/providers                 catalog + this user's saved keys (hints only) + active choice
PUT    /ai/providers/{id}            save/replace a key and/or change the model
DELETE /ai/providers/{id}            delete the saved key
POST   /ai/providers/{id}/test       check the saved key by listing the models it can use
PUT    /ai/active                    choose which saved provider to use (null = server default)
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_user
from app.core.config import get_settings
from app.core.security import limiter
from app.db.session import get_db
from app.models.user import AICredential, User
from app.services.ai import SUPPORTED_PROVIDERS, calls_today, server_key
from app.services.ai import credentials as creds
from app.services.ai.base import AIError
from app.services.ai.catalog import PROVIDERS, get_spec, valid_model

router = APIRouter(prefix="/ai", tags=["AI"])


class SaveKeyIn(BaseModel):
    api_key: Optional[str] = Field(None, max_length=512)
    model: Optional[str] = Field(None, max_length=120)


class TestIn(BaseModel):
    model: Optional[str] = Field(None, max_length=120)


class ActiveIn(BaseModel):
    provider: Optional[str] = Field(None, max_length=30)


def _http(e: AIError) -> HTTPException:
    status = {"invalid_request": 422, "configuration": 503, "missing_key": 400}.get(e.kind, 502)
    return HTTPException(status, e.message)


def _server(s) -> dict:
    spec = get_spec(s.AI_PROVIDER)
    return {"provider": s.AI_PROVIDER, "label": spec.label if spec else s.AI_PROVIDER, "model": s.AI_MODEL,
            "configured": bool(server_key(s)) and spec is not None}


def _active(db: Session, user: User, s) -> dict:
    row = creds.get_row(db, user.id, user.ai_provider) if user.ai_provider else None
    if row is not None:
        return {"provider": row.provider, "label": PROVIDERS[row.provider].label, "model": row.model,
                "configured": True, "source": "own"}
    srv = _server(s)
    return {**srv, "source": "server" if srv["configured"] else None}


@router.get("/status")
def ai_status(db: Session = Depends(get_db), user: User = Depends(require_user)):
    s = get_settings()
    active = _active(db, user, s)
    return {**active, "supported_providers": list(SUPPORTED_PROVIDERS), "timeout_sec": s.AI_TIMEOUT_SEC,
            "max_output_tokens": s.AI_MAX_OUTPUT_TOKENS,
            "daily_limit": s.AI_MAX_CALLS_PER_USER_PER_DAY if active["source"] == "server" else 0,
            "calls_last_24h": calls_today(db, user.id)}


@router.get("/providers")
def list_providers(db: Session = Depends(get_db), user: User = Depends(require_user)):
    s = get_settings()
    saved = {r.provider: creds.public(r) for r in db.query(AICredential).filter_by(user_id=user.id).all()}
    return {
        "providers": [{"id": p.id, "label": p.label, "description": p.description, "key_url": p.key_url,
                       "key_placeholder": p.key_prefix_hint, "default_model": p.default_model,
                       "suggested_models": list(p.suggested_models), "saved": saved.get(p.id)}
                      for p in PROVIDERS.values()],
        "active": _active(db, user, s),
        "selected": user.ai_provider,
        "server": _server(s),
        "can_save_keys": creds.encryption_available(),
        "server_daily_limit": s.AI_MAX_CALLS_PER_USER_PER_DAY,
        "calls_last_24h": calls_today(db, user.id),
    }


def _spec_or_404(provider_id: str):
    spec = get_spec(provider_id)
    if spec is None:
        raise HTTPException(404, "Unknown AI provider")
    return spec


@router.put("/providers/{provider_id}")
def save_key(provider_id: str, body: SaveKeyIn, db: Session = Depends(get_db), user: User = Depends(require_user)):
    spec = _spec_or_404(provider_id)
    if not limiter.hit(f"ai-save:{user.id}", 20, 60):
        raise HTTPException(429, "Too many changes. Wait a minute.")
    try:
        row = creds.save(db, user, spec.id, body.api_key if body.api_key else None, body.model)
    except AIError as e:
        db.rollback()
        raise _http(e)
    return creds.public(row)


@router.delete("/providers/{provider_id}")
def delete_key(provider_id: str, db: Session = Depends(get_db), user: User = Depends(require_user)):
    spec = _spec_or_404(provider_id)
    if not creds.delete(db, user, spec.id):
        raise HTTPException(404, "No saved key for this provider")
    return {"deleted": True, "selected": user.ai_provider}


@router.post("/providers/{provider_id}/test")
async def test_key(provider_id: str, body: TestIn, db: Session = Depends(get_db), user: User = Depends(require_user)):
    spec = _spec_or_404(provider_id)
    if not limiter.hit(f"ai-test:{user.id}", 10, 60):
        raise HTTPException(429, "Too many tests. Wait a minute.")
    row = creds.get_row(db, user.id, spec.id)
    if row is None:
        raise HTTPException(404, "Save an API key for this provider first")
    model = (body.model or row.model).strip()
    if not valid_model(model):
        raise HTTPException(422, "Invalid model name")
    try:
        models = await creds.provider_for(row, get_settings(), model).list_models()
        ok, err = True, None
    except AIError as e:
        models, ok, err = [], False, e.message
    available = model in models if models else None
    row.last_test_ok = ok and available is not False
    row.last_tested_at = datetime.now(timezone.utc)
    row.last_error = (err or (f"Model {model!r} is not in the list this key can use" if available is False else None))
    if row.last_error:
        row.last_error = row.last_error[:300]
    db.commit()
    return {"ok": ok, "model": model, "model_available": available, "models": models[:300],
            "error": row.last_error, "saved": creds.public(row)}


@router.put("/active")
def set_active(body: ActiveIn, db: Session = Depends(get_db), user: User = Depends(require_user)):
    if body.provider:
        spec = _spec_or_404(body.provider)
        if creds.get_row(db, user.id, spec.id) is None:
            raise HTTPException(400, "Save an API key for this provider first")
        user.ai_provider = spec.id
    else:
        user.ai_provider = None
    db.commit()
    return _active(db, user, get_settings())
