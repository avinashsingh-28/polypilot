"""Sign in with Google: flow integrity (state / nonce / PKCE), claim checks and account linking."""
import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlparse

import pytest

from app.core.config import get_settings
from app.models.user import User, UserSession
from tests.conftest import TEST_EMAIL, TEST_PASSWORD, login_client

API = "/api/v1"
CID = "test-client.apps.googleusercontent.com"


@pytest.fixture
def google(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "GOOGLE_CLIENT_ID", CID)
    monkeypatch.setattr(s, "GOOGLE_CLIENT_SECRET", "test-secret")
    calls = {"claims": {}, "exchanges": []}

    def fake_exchange(code, verifier):
        calls["exchanges"].append((code, verifier))
        return calls["token"]
    monkeypatch.setattr("app.services.google_oauth.exchange_code", fake_exchange)
    return calls


def _jwt(claims):
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{enc({'alg': 'RS256'})}.{enc(claims)}.sig"


def _start(c):
    r = c.get(f"{API}/auth/google/start", follow_redirects=False)
    assert r.status_code == 302
    q = {k: v[0] for k, v in parse_qs(urlparse(r.headers["location"]).query).items()}
    return r, q


def _callback(c, google, q, **claim_overrides):
    claims = {"iss": "https://accounts.google.com", "aud": CID, "exp": int(time.time()) + 300,
              "nonce": q["nonce"], "sub": "google-sub-1", "email": "Alice@Gmail.com", "email_verified": True}
    claims.update(claim_overrides)
    google["token"] = _jwt(claims)
    return c.get(f"{API}/auth/google/callback", params={"code": "auth-code", "state": q["state"]},
                 follow_redirects=False)


def test_disabled_without_configuration(anon_client):
    assert anon_client.get(f"{API}/auth/providers").json() == {"google": False}
    assert anon_client.get(f"{API}/auth/google/start", follow_redirects=False).status_code == 404


def test_start_redirects_with_pkce_state_and_nonce(anon_client, google):
    assert anon_client.get(f"{API}/auth/providers").json() == {"google": True}
    r, q = _start(anon_client)
    assert r.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert q["client_id"] == CID and q["response_type"] == "code" and q["code_challenge_method"] == "S256"
    assert q["redirect_uri"] == "http://localhost:5173/api/v1/auth/google/callback"
    assert len(q["state"]) >= 40 and len(q["nonce"]) >= 40 and "test-secret" not in r.headers["location"]
    cookie = [h for h in r.headers.get_list("set-cookie") if h.startswith("pp_oauth=")][0]
    assert "HttpOnly" in cookie and "Path=/api/v1/auth/google" in cookie and "samesite=lax" in cookie.lower()


def test_new_user_signs_in_and_pkce_verifier_matches(anon_client, google, db_session):
    _, q = _start(anon_client)
    r = _callback(anon_client, google, q)
    assert r.status_code == 302 and r.headers["location"] == "http://localhost:5173/"
    me = anon_client.get(f"{API}/auth/me").json()
    assert me["email"] == "alice@gmail.com"
    u = db_session.query(User).filter_by(email="alice@gmail.com").one()
    assert u.google_sub == "google-sub-1" and u.email_verified and u.password_hash is None
    code, verifier = google["exchanges"][0]
    assert code == "auth-code"
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == q["code_challenge"]
    # A Google-only account cannot be signed into with any password.
    assert anon_client.post(f"{API}/auth/login", json={"email": "alice@gmail.com", "password": "x" * 12}).status_code == 401
    # Second sign-in finds the same account by sub, even if the Google email changed.
    _, q2 = _start(anon_client)
    _callback(anon_client, google, q2, email="renamed@gmail.com")
    assert db_session.query(User).count() == 1


def test_callback_rejects_forged_or_missing_state(anon_client, google):
    _, q = _start(anon_client)
    r = anon_client.get(f"{API}/auth/google/callback", params={"code": "c", "state": "attacker-state"},
                        follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].endswith("?auth_error=google_state")
    anon_client.cookies.clear()                                   # no flow cookie at all
    r = _callback(anon_client, google, q)
    assert r.headers["location"].endswith("?auth_error=google_state")
    assert anon_client.get(f"{API}/auth/me").status_code == 401 and google["exchanges"] == []


def test_tampered_flow_cookie_is_rejected(anon_client, google):
    _, q = _start(anon_client)
    raw = anon_client.cookies.get("pp_oauth")
    anon_client.cookies.clear()
    anon_client.cookies.set("pp_oauth", raw[:-4] + "0000", path="/api/v1/auth/google")
    assert _callback(anon_client, google, q).headers["location"].endswith("?auth_error=google_state")


@pytest.mark.parametrize("override,err", [
    ({"aud": "someone-else"}, "google_failed"),
    ({"iss": "https://evil.example"}, "google_failed"),
    ({"nonce": "replayed-nonce"}, "google_failed"),
    ({"exp": int(time.time()) - 3600}, "google_failed"),
    ({"email_verified": False}, "google_unverified"),
])
def test_bad_id_token_claims_are_rejected(anon_client, google, override, err):
    _, q = _start(anon_client)
    r = _callback(anon_client, google, q, **override)
    assert r.headers["location"].endswith(f"?auth_error={err}")
    assert anon_client.get(f"{API}/auth/me").status_code == 401


def test_user_denied_consent(anon_client, google):
    _start(anon_client)
    r = anon_client.get(f"{API}/auth/google/callback", params={"error": "access_denied"}, follow_redirects=False)
    assert r.headers["location"].endswith("?auth_error=google_denied")


def test_linking_unverified_password_account_drops_password_and_sessions(anon_client, google, db_session):
    """Pre-hijacking defence: a password set by whoever registered the address first stops working."""
    login_client(anon_client)                                      # TEST_EMAIL registered with a password
    old = anon_client.cookies.get("pp_session")
    anon_client.cookies.clear()
    _, q = _start(anon_client)
    r = _callback(anon_client, google, q, email=TEST_EMAIL)
    assert r.headers["location"] == "http://localhost:5173/"
    assert anon_client.get(f"{API}/auth/me").json()["email"] == TEST_EMAIL
    u = db_session.query(User).filter_by(email=TEST_EMAIL).one()
    assert u.password_hash is None and u.google_sub == "google-sub-1" and u.email_verified
    assert anon_client.post(f"{API}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}).status_code == 401
    anon_client.cookies.clear()                                    # send only the old session cookie
    anon_client.cookies.set("pp_session", old)
    assert anon_client.get(f"{API}/auth/me").status_code == 401
    assert db_session.query(User).count() == 1


def test_linking_verified_account_keeps_password(anon_client, google, db_session):
    login_client(anon_client)
    u = db_session.query(User).filter_by(email=TEST_EMAIL).one()
    u.email_verified = True
    db_session.commit()
    _, q = _start(anon_client)
    _callback(anon_client, google, q, email=TEST_EMAIL)
    db_session.refresh(u)
    assert u.google_sub == "google-sub-1" and u.password_hash is not None
    assert anon_client.post(f"{API}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}).status_code == 200


def test_email_linked_to_a_different_google_account_is_refused(anon_client, google, db_session):
    db_session.add(User(email="bob@gmail.com", google_sub="other-sub", email_verified=True))
    db_session.commit()
    _, q = _start(anon_client)
    r = _callback(anon_client, google, q, email="bob@gmail.com")
    assert r.headers["location"].endswith("?auth_error=google_conflict")


def test_registration_closed_and_disabled_account(anon_client, google, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "REGISTRATION_OPEN", False)
    _, q = _start(anon_client)
    assert _callback(anon_client, google, q).headers["location"].endswith("?auth_error=registration_closed")
    db_session.add(User(email="alice@gmail.com", google_sub="google-sub-1", email_verified=True, is_active=False))
    db_session.commit()
    _, q = _start(anon_client)
    assert _callback(anon_client, google, q).headers["location"].endswith("?auth_error=account_disabled")
    assert db_session.query(UserSession).count() == 0


def test_reset_password_marks_email_verified(anon_client, monkeypatch, db_session):
    links = []
    monkeypatch.setattr("app.services.email.send_password_reset", lambda e, l, t: links.append(l))
    anon_client.post(f"{API}/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    anon_client.post(f"{API}/auth/forgot-password", json={"email": TEST_EMAIL})
    token = links[-1].split("reset_token=")[1]
    anon_client.post(f"{API}/auth/reset-password", json={"token": token, "password": "fresh-passphrase-31"})
    assert db_session.query(User).filter_by(email=TEST_EMAIL).one().email_verified


def test_production_requires_https_and_both_google_values():
    from app.core.config import Settings
    base = dict(_env_file=None, ENVIRONMENT="production", AUTH_SECRET_KEY="k" * 40, COOKIE_SECURE=True,
                CORS_ORIGINS=["https://polypilot.example"], DATABASE_URL="postgresql://u:p@db/x")
    assert any("both" in e for e in Settings(**base, GOOGLE_CLIENT_ID="id").production_problems())
    http = Settings(**base, GOOGLE_CLIENT_ID="id", GOOGLE_CLIENT_SECRET="s", PUBLIC_APP_URL="http://x.example")
    assert any("https://" in e for e in http.production_problems())
    ok = Settings(**base, GOOGLE_CLIENT_ID="id", GOOGLE_CLIENT_SECRET="s", PUBLIC_APP_URL="https://x.example")
    assert ok.production_problems() == []
