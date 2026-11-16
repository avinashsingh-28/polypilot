"""
Polygon credential storage.

Precedence: POLYGON_API_KEY/POLYGON_API_SECRET environment variables, then credentials saved
through the UI. Saved credentials are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) using
POLYGON_CREDENTIALS_KEY; without that key, saving is refused (never stored in plaintext).
Secrets are never returned by any function used by API routes.
"""
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.polygon import PolygonAccount, PolygonOperation
from app.models.user import User
from app.services.polygon.client import Credentials, PolygonClient, PolygonError, validate_base_url


def _now():
    return datetime.now(timezone.utc)


def _fernet() -> Optional[Fernet]:
    key = get_settings().POLYGON_CREDENTIALS_KEY
    if not key:
        return None
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError):
        raise PolygonError("configuration", "POLYGON_CREDENTIALS_KEY is not a valid Fernet key")


def _hint(api_key: str) -> str:
    return f"{api_key[:4]}…{api_key[-2:]}" if len(api_key) > 8 else "…"


def env_credentials_allowed(user: User) -> bool:
    """Env credentials are one shared Polygon account: in production only for the configured
    owner email; in development for any local user."""
    s = get_settings()
    if not (s.POLYGON_API_KEY and s.POLYGON_API_SECRET):
        return False
    if s.POLYGON_ENV_CREDENTIALS_EMAIL:
        return user.email == s.POLYGON_ENV_CREDENTIALS_EMAIL.strip().lower()
    return not s.is_production


def account_row(db: Session, source: str, user: User) -> PolygonAccount:
    row = db.query(PolygonAccount).filter_by(source=source, user_id=user.id).first()
    if row is None:
        row = PolygonAccount(source=source, user_id=user.id)
        db.add(row)
        db.flush()
    return row


def load_credentials(db: Session, user: User) -> Optional[Credentials]:
    s = get_settings()
    if env_credentials_allowed(user):
        return Credentials(s.POLYGON_API_KEY, s.POLYGON_API_SECRET, "env")
    row = db.query(PolygonAccount).filter_by(source="stored", user_id=user.id).first()
    if not row or not row.api_key_encrypted or not row.api_secret_encrypted:
        return None
    f = _fernet()
    if f is None:
        raise PolygonError("configuration", "Stored Polygon credentials exist but POLYGON_CREDENTIALS_KEY is not set")
    try:
        return Credentials(f.decrypt(row.api_key_encrypted.encode()).decode(),
                           f.decrypt(row.api_secret_encrypted.encode()).decode(), "stored")
    except InvalidToken:
        raise PolygonError("configuration", "Stored Polygon credentials cannot be decrypted with the current "
                                            "POLYGON_CREDENTIALS_KEY; save them again")


def store_credentials(db: Session, user: User, api_key: str, api_secret: str) -> PolygonAccount:
    f = _fernet()
    if f is None:
        raise PolygonError("configuration", "Saving credentials requires POLYGON_CREDENTIALS_KEY (a Fernet key) in "
                                            "backend/.env; alternatively set POLYGON_API_KEY/POLYGON_API_SECRET there")
    row = account_row(db, "stored", user)
    row.api_key_encrypted = f.encrypt(api_key.encode()).decode()
    row.api_secret_encrypted = f.encrypt(api_secret.encode()).decode()
    row.key_hint = _hint(api_key)
    row.last_test_at = row.last_test_ok = row.last_test_kind = row.last_test_message = None
    db.commit()
    return row


def delete_stored(db: Session, user: User) -> None:
    row = db.query(PolygonAccount).filter_by(source="stored", user_id=user.id).first()
    if row:
        db.delete(row)
        db.commit()


def connection_status(db: Session, user: User) -> dict:
    s = get_settings()
    env = env_credentials_allowed(user)
    stored = db.query(PolygonAccount).filter_by(source="stored", user_id=user.id).first()
    has_stored = bool(stored and stored.api_secret_encrypted)
    source = "env" if env else ("stored" if has_stored else None)
    row = db.query(PolygonAccount).filter_by(source=source, user_id=user.id).first() if source else None
    return {
        "configured": source is not None,
        "source": source,
        "key_hint": _hint(s.POLYGON_API_KEY) if env else (stored.key_hint if has_stored else None),
        "env_overrides_stored": env and has_stored,
        "encryption_available": bool(s.POLYGON_CREDENTIALS_KEY),
        "base_url": s.POLYGON_API_BASE_URL,
        "last_test_at": row.last_test_at if row else None,
        "last_test_ok": row.last_test_ok if row else None,
        "last_test_kind": row.last_test_kind if row else None,
        "last_test_message": row.last_test_message if row else None,
        "last_success_at": row.last_success_at if row else None,
        "accessible_problems": row.accessible_problems if row else None,
    }


def operation_recorder(db: Session, problem_id: Optional[uuid.UUID] = None,
                       sync_run_id: Optional[uuid.UUID] = None) -> Callable[[dict], None]:
    def record(op: dict) -> None:
        db.add(PolygonOperation(problem_id=problem_id, sync_run_id=sync_run_id, method=op["method"],
                                write=op["write"], params=op["params"], status=op["status"],
                                http_status=op.get("http_status"), duration_ms=op.get("duration_ms"),
                                response_summary=(op.get("response_summary") or "")[:1000] or None,
                                error_kind=op.get("error_kind"), error_message=op.get("error_message")))
        db.commit()
    return record


def make_client(db: Session, user: User, problem_id: Optional[uuid.UUID] = None,
                sync_run_id: Optional[uuid.UUID] = None,
                transport: Optional[httpx.BaseTransport] = None) -> PolygonClient:
    s = get_settings()
    validate_base_url(s.POLYGON_API_BASE_URL)
    return PolygonClient(load_credentials(db, user), s.POLYGON_API_BASE_URL, timeout=s.POLYGON_TIMEOUT_SEC,
                         transport=transport, min_interval=s.POLYGON_MIN_INTERVAL_SEC,
                         on_operation=operation_recorder(db, problem_id, sync_run_id))


def test_connection(db: Session, user: User, transport: Optional[httpx.BaseTransport] = None) -> dict:
    """Read-only check: problems.list. Records the outcome (no secrets)."""
    creds = None
    try:
        creds = load_credentials(db, user)
        if creds is None:
            raise PolygonError("missing_credentials", "Polygon API key/secret are not configured")
        with make_client(db, user, transport=transport) as c:
            problems = c.call("problems.list")
        result = {"ok": True, "kind": "connected", "accessible_problems": len(problems or []),
                  "message": f"Connected. {len(problems or [])} problems accessible with this key."}
    except PolygonError as e:
        hints = {
            "missing_credentials": "Set POLYGON_API_KEY and POLYGON_API_SECRET in backend/.env or save them in Settings.",
            "invalid_credentials": "Polygon rejected the API key or signature. Check the key/secret pair.",
            "clock_skew": "Polygon rejected the request time. Synchronize this computer's clock.",
            "permission_denied": "The key is valid but lacks permission for this operation.",
            "network": "Could not reach polygon.codeforces.com.", "timeout": "Polygon did not respond in time.",
            "rate_limited": "Polygon rate limit reached; try again shortly.",
        }
        result = {"ok": False, "kind": e.kind, "accessible_problems": None,
                  "message": f"{e.message}. {hints.get(e.kind, '')}".strip()}
    if creds is not None or result["kind"] != "missing_credentials":
        row = account_row(db, creds.source if creds else "env", user)
        row.last_test_at, row.last_test_ok = _now(), result["ok"]
        row.last_test_kind, row.last_test_message = result["kind"], result["message"][:1000]
        if result["ok"]:
            row.last_success_at, row.accessible_problems = _now(), result["accessible_problems"]
        db.commit()
    return result
