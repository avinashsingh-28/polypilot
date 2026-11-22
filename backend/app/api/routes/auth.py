"""
Authentication API (cookie sessions).

POST /auth/register   always returns the same generic response (no account enumeration);
                      does not log the user in.
POST /auth/login      generic error for unknown email / wrong password; rate limited.
POST /auth/logout     revokes the server-side session and clears cookies.
GET  /auth/me         current user (401 if not logged in).
GET  /auth/csrf       re-issues the CSRF cookie for the current session.
POST /auth/forgot-password  always the same response; emails a single-use reset link if the account exists.
POST /auth/reset-password   sets a new password with a valid link; signs out every session.
GET  /auth/providers        which external sign-in providers are configured.
GET  /auth/google/start     redirects to Google (OpenID Connect + PKCE).
GET  /auth/google/callback  Google redirects back here; signs in and redirects to the app.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import load_session, require_user
from app.core.config import get_settings
from app.core.security import (csrf_for, hash_password, limiter, needs_rehash, new_session_token, normalize_email,
                               validate_email, validate_password, verify_password)
from app.db.session import get_db
from app.models.user import PasswordResetToken, User, UserSession

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
    _start_session(db, user, request, response)
    return {"user": _user_out(user)}


def _start_session(db: Session, user: User, request: Request, response: Response) -> None:
    s = get_settings()
    now = datetime.now(timezone.utc)
    token, token_hash = new_session_token()        # fresh token on every login (no fixation)
    db.add(UserSession(user_id=user.id, token_hash=token_hash, created_at=now, last_seen_at=now,
                       expires_at=now + timedelta(days=s.SESSION_ABSOLUTE_TIMEOUT_DAYS),
                       user_agent=(request.headers.get("user-agent") or "")[:200]))
    user.last_login_at = now
    db.commit()
    _set_cookies(response, token, token_hash)


# ── Sign in with Google ──────────────────────────────────────────────────────
@router.get("/providers")
def providers():
    from app.services import google_oauth
    return {"google": google_oauth.enabled()}


def _flow_cookie_path() -> str:
    return f"{get_settings().API_V1_PREFIX}/auth/google"


@router.get("/google/start")
def google_start(request: Request):
    from fastapi.responses import RedirectResponse
    from app.services import google_oauth
    s = get_settings()
    if not google_oauth.enabled():
        raise HTTPException(404, "Google sign-in is not configured")
    _rate_limit(request, "google")
    url, cookie = google_oauth.new_flow()
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie(google_oauth.FLOW_COOKIE, cookie, max_age=google_oauth.FLOW_TTL_SEC, httponly=True,
                    secure=s.COOKIE_SECURE, samesite="lax", path=_flow_cookie_path())
    return resp


@router.get("/google/callback")
def google_callback(request: Request, db: Session = Depends(get_db), code: str | None = None,
                    state: str | None = None, error: str | None = None):
    """Google redirects here. Always ends with a redirect back to the app (errors as ?auth_error=)."""
    from fastapi.responses import RedirectResponse
    from app.services import google_oauth
    from app.services.google_oauth import GoogleAuthError
    s = get_settings()
    if not google_oauth.enabled():
        raise HTTPException(404, "Google sign-in is not configured")
    app_url = s.PUBLIC_APP_URL.rstrip("/") + "/"

    def done(err: str | None = None) -> RedirectResponse:
        resp = RedirectResponse(app_url + (f"?auth_error={err}" if err else ""), status_code=302)
        resp.delete_cookie(google_oauth.FLOW_COOKIE, path=_flow_cookie_path(), secure=s.COOKIE_SECURE,
                           samesite="lax")
        if err:
            log.warning("google sign-in failed", extra={"reason": err, "client": _client_ip(request)})
        return resp

    _rate_limit(request, "google")
    if error:
        return done("google_denied")
    try:
        flow = google_oauth.read_flow(request.cookies.get(google_oauth.FLOW_COOKIE), state)
        if not code or len(code) > 2048:
            raise GoogleAuthError("google_failed")
        claims = google_oauth.verify_id_token(google_oauth.exchange_code(code, flow["verifier"]), flow["nonce"])
    except GoogleAuthError as e:
        return done(e.code)

    sub, email = str(claims["sub"]), normalize_email(claims["email"])
    user = db.query(User).filter_by(google_sub=sub).first()
    if user is None:
        user = db.query(User).filter_by(email=email).first()
        if user is not None and not user.is_active:
            return done("account_disabled")
        if user is not None and user.google_sub and user.google_sub != sub:
            return done("google_conflict")            # email already linked to another Google account
        if user is not None:
            if not user.email_verified:
                # Pre-hijacking defence: someone may have registered this address with a password
                # before its real owner arrived. Google proves the owner, so the unproven password and
                # every existing session are dropped. The owner can set a password via "Forgot password".
                user.password_hash = None
                db.query(UserSession).filter(UserSession.user_id == user.id,
                                             UserSession.revoked_at.is_(None)).update(
                    {"revoked_at": datetime.now(timezone.utc)})
            user.google_sub = sub
            user.email_verified = True
            log.info("google identity linked to existing account")
        else:
            if not s.REGISTRATION_OPEN:
                return done("registration_closed")
            if validate_email(email):
                return done("google_failed")
            user = User(email=email, password_hash=None, google_sub=sub, email_verified=True)
            db.add(user)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                return done("google_failed")
            log.info("user registered via google")
    if not user.is_active:
        return done("account_disabled")
    resp = done()
    _start_session(db, user, request, resp)
    return resp


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


# ── Forgot / reset password ──────────────────────────────────────────────────
GENERIC_FORGOT = ("If an account exists for this email, a password reset link has been sent. "
                  "It expires in {ttl} minutes.")
INVALID_LINK = "This reset link is invalid or has expired. Request a new one."


class ForgotIn(BaseModel):
    email: str = Field(..., max_length=254)


class ResetIn(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)
    password: str = Field(..., max_length=128)


@router.post("/forgot-password", status_code=202)
def forgot_password(body: ForgotIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Same response, status and (roughly) timing whether or not the account exists."""
    from app.core.security import hash_token
    from app.services.email import send_password_reset
    s = get_settings()
    _rate_limit(request, "forgot")
    email = normalize_email(body.email)
    message = {"message": GENERIC_FORGOT.format(ttl=s.PASSWORD_RESET_TTL_MIN)}
    if validate_email(email):
        return message
    # At most 3 reset emails per address per hour (silently ignored beyond that).
    if not limiter.hit(f"forgot:email:{email}", 3, 3600):
        return message
    user = db.query(User).filter_by(email=email).first()
    if user is None or not user.is_active:
        return message
    now = datetime.now(timezone.utc)
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id,
                                        PasswordResetToken.used_at.is_(None)).update({"used_at": now})
    token = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(token), created_at=now,
                              expires_at=now + timedelta(minutes=s.PASSWORD_RESET_TTL_MIN)))
    db.commit()
    link = f"{s.PUBLIC_APP_URL.rstrip('/')}/?reset_token={token}"
    background.add_task(send_password_reset, user.email, link, s.PASSWORD_RESET_TTL_MIN)  # sent after the response
    log.info("password reset requested")
    return message


@router.post("/reset-password")
def reset_password(body: ResetIn, request: Request, response: Response, db: Session = Depends(get_db)):
    from app.core.security import hash_token
    _rate_limit(request, "reset")
    now = datetime.now(timezone.utc)
    rec = db.query(PasswordResetToken).filter_by(token_hash=hash_token(body.token)).first()
    if rec is None or rec.used_at is not None:
        raise HTTPException(400, INVALID_LINK)
    expires = rec.expires_at if rec.expires_at.tzinfo else rec.expires_at.replace(tzinfo=timezone.utc)
    if expires <= now:
        raise HTTPException(400, INVALID_LINK)
    user = db.get(User, rec.user_id)
    if user is None or not user.is_active:
        raise HTTPException(400, INVALID_LINK)
    err = validate_password(body.password, user.email)
    if err:
        raise HTTPException(422, err)
    user.password_hash = hash_password(body.password)
    user.email_verified = True                     # the link was delivered to this address
    rec.used_at = now
    # Every existing session is signed out (e.g. an attacker who knew the old password).
    db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)).update(
        {"revoked_at": now})
    limiter.reset(f"login-fail:{user.email}")
    db.commit()
    _clear_cookies(response)
    log.info("password reset completed")
    return {"message": "Your password has been changed. Sign in with your new password."}
