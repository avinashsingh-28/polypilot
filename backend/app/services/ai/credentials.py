"""
Users' own AI provider API keys.

Keys are encrypted with Fernet (AES-128-CBC + HMAC-SHA256). The encryption key is
AI_CREDENTIALS_KEY, else POLYGON_CREDENTIALS_KEY; in development only, a key derived from
AUTH_SECRET_KEY is used when neither is set. Without any of these, saving is refused — a key is
never stored in plaintext. No function used by API routes returns a decrypted key.
"""
import base64
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import AICredential, User
from app.services.ai.base import AIError, AIProvider
from app.services.ai.catalog import get_spec, valid_model


def _now():
    return datetime.now(timezone.utc)


def _fernet() -> Fernet:
    s = get_settings()
    key = s.AI_CREDENTIALS_KEY or s.POLYGON_CREDENTIALS_KEY
    if key:
        try:
            return Fernet(key.encode())
        except (ValueError, TypeError):
            raise AIError("configuration", "AI_CREDENTIALS_KEY is not a valid Fernet key")
    if not s.is_production and len(s.AUTH_SECRET_KEY) >= 16:
        derived = hashlib.sha256(f"polypilot-ai-credentials:{s.AUTH_SECRET_KEY}".encode()).digest()
        return Fernet(base64.urlsafe_b64encode(derived))
    raise AIError("configuration", "Saving API keys is disabled: the server has no encryption key "
                                   "(set AI_CREDENTIALS_KEY in the backend environment).")


def encryption_available() -> bool:
    try:
        _fernet()
        return True
    except AIError:
        return False


def key_hint(api_key: str) -> str:
    return f"…{api_key[-4:]}" if len(api_key) >= 12 else "…"


def validate_key(api_key: str) -> Optional[str]:
    if not api_key or len(api_key) < 8 or len(api_key) > 512:
        return "API key must be 8–512 characters"
    if any(c.isspace() or not c.isprintable() for c in api_key):
        return "API key must not contain spaces or control characters"
    return None


def get_row(db: Session, user_id: uuid.UUID, provider: str) -> Optional[AICredential]:
    return db.query(AICredential).filter_by(user_id=user_id, provider=provider).first()


def save(db: Session, user: User, provider: str, api_key: Optional[str], model: Optional[str]) -> AICredential:
    """Create or update. A new key is required on create; on update, a missing key keeps the old one.
    The first saved provider becomes the user's active one."""
    spec = get_spec(provider)
    if spec is None:
        raise AIError("invalid_request", "Unknown provider")
    model = (model or "").strip() or spec.default_model
    if not valid_model(model):
        raise AIError("invalid_request", "Invalid model name")
    row = get_row(db, user.id, spec.id)
    if api_key is not None:
        api_key = api_key.strip()
        err = validate_key(api_key)
        if err:
            raise AIError("invalid_request", err)
    elif row is None:
        raise AIError("invalid_request", "API key is required")
    if row is None:
        row = AICredential(user_id=user.id, provider=spec.id, model=model)
        db.add(row)
    if api_key is not None:
        row.api_key_encrypted = _fernet().encrypt(api_key.encode()).decode()
        row.key_hint = key_hint(api_key)
        row.last_test_ok, row.last_tested_at, row.last_error = None, None, None
    if row.model != model:
        row.model = model
        row.last_test_ok, row.last_error = None, None
    row.updated_at = _now()
    if not user.ai_provider:
        user.ai_provider = spec.id
    db.commit()
    return row


def delete(db: Session, user: User, provider: str) -> bool:
    row = get_row(db, user.id, provider)
    if row is None:
        return False
    db.delete(row)
    if user.ai_provider == provider:
        other = db.query(AICredential).filter(AICredential.user_id == user.id,
                                              AICredential.provider != provider).first()
        user.ai_provider = other.provider if other else None
    db.commit()
    return True


def decrypt(row: AICredential) -> str:
    try:
        return _fernet().decrypt(row.api_key_encrypted.encode()).decode()
    except InvalidToken:
        raise AIError("configuration", "Your saved API key can no longer be decrypted (the server's encryption "
                                       "key changed). Please save it again.")


def provider_for(row: AICredential, settings, model: Optional[str] = None) -> AIProvider:
    from app.services.ai import build_provider
    return build_provider(row.provider, decrypt(row), model or row.model, settings)


def load_user_provider(db: Session, user_id: uuid.UUID, settings) -> Optional[AIProvider]:
    user = db.get(User, user_id)
    if user is None or not user.ai_provider:
        return None
    row = get_row(db, user.id, user.ai_provider)
    if row is None:
        return None
    return provider_for(row, settings)


def public(row: AICredential) -> dict:
    return {"provider": row.provider, "key_hint": row.key_hint, "model": row.model,
            "updated_at": row.updated_at, "last_test_ok": row.last_test_ok,
            "last_tested_at": row.last_tested_at, "last_error": row.last_error}
