"""
Sign in with Google — OpenID Connect authorization-code flow with PKCE, state and nonce.

Security notes
- The browser never sees the client secret or Google's tokens; the code is exchanged server-side.
- state + nonce + PKCE verifier live in a short-lived, HMAC-signed, HttpOnly cookie scoped to the
  callback path, so a forged or replayed callback is rejected.
- The ID token comes straight from Google's token endpoint over TLS, which OpenID Connect Core
  §3.1.3.7 allows in place of signature verification; issuer, audience, expiry, nonce and
  email_verified are still checked.
- Google's tokens are discarded after the claims are read; nothing from Google is logged.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.security import secret_key

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105  (public endpoint, not a secret)
ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
FLOW_COOKIE = "pp_oauth"
FLOW_TTL_SEC = 600


class GoogleAuthError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def enabled() -> bool:
    s = get_settings()
    return bool(s.GOOGLE_CLIENT_ID and s.GOOGLE_CLIENT_SECRET)


def redirect_uri() -> str:
    s = get_settings()
    return s.GOOGLE_REDIRECT_URI or f"{s.PUBLIC_APP_URL.rstrip('/')}{s.API_V1_PREFIX}/auth/google/callback"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload: str) -> str:
    return hmac.new(secret_key().encode(), f"google-oauth:{payload}".encode(), hashlib.sha256).hexdigest()


def new_flow() -> tuple[str, str]:
    """Returns (authorization URL, signed flow cookie value)."""
    s = get_settings()
    flow = {"state": secrets.token_urlsafe(32), "nonce": secrets.token_urlsafe(32),
            "verifier": secrets.token_urlsafe(64), "exp": int(time.time()) + FLOW_TTL_SEC}
    challenge = _b64(hashlib.sha256(flow["verifier"].encode()).digest())
    url = AUTH_URL + "?" + urlencode({
        "client_id": s.GOOGLE_CLIENT_ID, "redirect_uri": redirect_uri(), "response_type": "code",
        "scope": "openid email profile", "state": flow["state"], "nonce": flow["nonce"],
        "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account",
    })
    payload = _b64(json.dumps(flow, separators=(",", ":")).encode())
    return url, f"{payload}.{_sign(payload)}"


def read_flow(cookie: Optional[str], state: Optional[str]) -> dict:
    """Validates the flow cookie against the returned state. Raises GoogleAuthError('google_state')."""
    try:
        payload, sig = (cookie or "").rsplit(".", 1)
        if not hmac.compare_digest(sig, _sign(payload)):
            raise ValueError
        flow = json.loads(_unb64(payload))
        if flow["exp"] < time.time() or not state or not hmac.compare_digest(flow["state"], state):
            raise ValueError
        return flow
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise GoogleAuthError("google_state")


def exchange_code(code: str, verifier: str) -> str:
    """Exchanges the authorization code for an ID token (string). Raises GoogleAuthError('google_failed')."""
    s = get_settings()
    try:
        r = httpx.post(TOKEN_URL, timeout=10.0, data={
            "code": code, "client_id": s.GOOGLE_CLIENT_ID, "client_secret": s.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri(), "grant_type": "authorization_code", "code_verifier": verifier,
        })
    except httpx.HTTPError:
        raise GoogleAuthError("google_failed")
    if r.status_code != 200:
        raise GoogleAuthError("google_failed")
    try:
        id_token = r.json()["id_token"]
    except (ValueError, KeyError):
        raise GoogleAuthError("google_failed")
    if not isinstance(id_token, str):
        raise GoogleAuthError("google_failed")
    return id_token


def verify_id_token(id_token: str, nonce: str) -> dict:
    """Checks the claims of an ID token received directly from Google's token endpoint."""
    s = get_settings()
    try:
        claims = json.loads(_unb64(id_token.split(".")[1]))
    except (IndexError, ValueError):
        raise GoogleAuthError("google_failed")
    now = time.time()
    aud = claims.get("aud")
    aud_ok = aud == s.GOOGLE_CLIENT_ID or (isinstance(aud, list) and s.GOOGLE_CLIENT_ID in aud)
    if (claims.get("iss") not in ISSUERS or not aud_ok or not isinstance(claims.get("exp"), (int, float))
            or claims["exp"] < now - 60 or not isinstance(claims.get("nonce"), str)
            or not hmac.compare_digest(claims["nonce"], nonce) or not claims.get("sub")):
        raise GoogleAuthError("google_failed")
    if claims.get("email_verified") not in (True, "true") or not claims.get("email"):
        raise GoogleAuthError("google_unverified")
    return claims
