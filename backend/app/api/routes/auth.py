"""
Authentication API (cookie sessions).

POST /auth/register   always returns the same generic response (no account enumeration);
                      does not log the user in.
POST /auth/login      generic error for unknown email / wrong password; rate limited.
POST /auth/logout     revokes the server-side session and clears cookies.
GET  /auth/me         current user (401 if not logged in).
GET  /auth/csrf       re-issues the CSRF cookie for the current session.
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import load_session, require_user
from app.core.config import get_settings
from app.core.security import (csrf_for, hash_password, limiter, needs_rehash, new_session_token, normalize_email,
                               validate_email, validate_password, verify_password)
from app.db.session import get_db
from app.models.user import User, UserSession

router = APIRouter(prefix="/auth", tags=["Auth"])
log = logging.getLogger("polypilot.auth")
GENERIC_REGISTER = "If this email can be registered, the account has been created. Please sign in."


class Credentials(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=128)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _rate_limit(request: Request, action: str) -> None:
    s = get_settings()
    if not limiter.hit(f"{action}:ip:{_client_ip(request)}", s.AUTH_RATE_LIMIT_PER_MIN, 60):
        log.warning("auth rate limit", extra={"action": action, "client": _client_ip(request)})
        raise HTTPException(429, "Too many attempts. Please wait a minute and try again.")


def _set_cookies(response: Response, token: str, token_hash: str) -> None:
    s = get_settings()
    max_age = s.SESSION_ABSOLUTE_TIMEOUT_DAYS * 86400
    common = dict(max_age=max_age, secure=s.COOKIE_SECURE, samesite=s.COOKIE_SAMESITE.lower(), path="/")
    response.set_cookie(s.SESSION_COOKIE_NAME, token, httponly=True, **common)
    response.set_cookie(s.CSRF_COOKIE_NAME, csrf_for(token_hash), httponly=False, **common)


def _clear_cookies(response: Response) -> None:
    s = get_settings()
    for name in (s.SESSION_COOKIE_NAME, s.CSRF_COOKIE_NAME):
        response.delete_cookie(name, path="/", secure=s.COOKIE_SECURE, samesite=s.COOKIE_SAMESITE.lower())


def _user_out(u: User) -> dict:
    return {"id": str(u.id), "email": u.email, "created_at": u.created_at}


@router.post("/register", status_code=202)
def register(body: Credentials, request: Request, db: Session = Depends(get_db)):
    s = get_settings()
    _rate_limit(request, "register")
    if not s.REGISTRATION_OPEN:
        raise HTTPException(403, "Registration is closed on this instance")
    email = normalize_email(body.email)
    err = validate_email(email) or validate_password(body.password, email)
    if err:
        raise HTTPException(422, err)
    pw_hash = hash_password(body.password)        # always hash: equal timing for existing emails
    if db.query(User.id).filter_by(email=email).first() is None:
        db.add(User(email=email, password_hash=pw_hash))
        try:
            db.commit()
            log.info("user registered")
        except IntegrityError:
            db.rollback()
    return {"message": GENERIC_REGISTER}


@router.post("/login")
def login(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    _rate_limit(request, "login")
    email = normalize_email(body.email)
    fail_key = f"login-fail:{email}"
    if not limiter.hit(fail_key, s.AUTH_MAX_FAILURES_PER_EMAIL, 900, record=False):
        raise HTTPException(429, "Too many failed attempts for this account. Try again in 15 minutes.")
    user = db.query(User).filter_by(email=email).first()
    ok = verify_password(user.password_hash if user else None, body.password)
    if not ok or not user.is_active:
        limiter.hit(fail_key, s.AUTH_MAX_FAILURES_PER_EMAIL, 900)
        log.warning("login failed", extra={"client": _client_ip(request)})
        raise HTTPException(401, "Invalid email or password")
    limiter.reset(fail_key)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    now = datetime.now(timezone.utc)
    token, token_hash = new_session_token()        # fresh token on every login (no fixation)
    db.add(UserSession(user_id=user.id, token_hash=token_hash, created_at=now, last_seen_at=now,
                       expires_at=now + timedelta(days=s.SESSION_ABSOLUTE_TIMEOUT_DAYS),
                       user_agent=(request.headers.get("user-agent") or "")[:200]))
    user.last_login_at = now
    db.commit()
    _set_cookies(response, token, token_hash)
    return {"user": _user_out(user)}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    sess = load_session(db, request.cookies.get(s.SESSION_COOKIE_NAME))
    if sess is not None:
        # Logout is CSRF-protected too, so a third-party page cannot force a logout.
        from app.core.security import csrf_valid
        if not csrf_valid(sess.token_hash, request.headers.get("X-CSRF-Token")):
            raise HTTPException(403, "CSRF token missing or invalid")
        sess.revoked_at = datetime.now(timezone.utc)
        db.commit()
    _clear_cookies(response)
    return {"message": "Signed out"}


@router.get("/me")
def me(user: User = Depends(require_user)):
    return _user_out(user)


@router.get("/csrf")
def csrf(request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    sess = load_session(db, request.cookies.get(s.SESSION_COOKIE_NAME))
    if sess is None:
        raise HTTPException(401, "Not authenticated")
    response.set_cookie(s.CSRF_COOKIE_NAME, csrf_for(sess.token_hash), httponly=False, secure=s.COOKIE_SECURE,
                        samesite=s.COOKIE_SAMESITE.lower(), path="/",
                        max_age=s.SESSION_ABSOLUTE_TIMEOUT_DAYS * 86400)
    return {"ok": True}
