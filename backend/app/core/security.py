"""
Authentication primitives.

* Passwords: Argon2id (argon2-cffi defaults: time_cost=3, memory_cost=64 MiB, parallelism=4).
* Sessions: opaque 256-bit random token in an HttpOnly cookie; only SHA-256(token) is stored, so a
  database leak does not reveal usable tokens. Sessions have idle and absolute expiry and are
  revoked on logout.
* CSRF: synchronizer token derived as HMAC(AUTH_SECRET_KEY, session token hash), exposed in a
  JS-readable cookie and required in the X-CSRF-Token header for unsafe methods.
* Rate limiting: in-memory sliding windows (per process — see docs/SECURITY.md).
"""
import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("timing-equalizer-password")
_dev_secret = secrets.token_urlsafe(48)   # per-process fallback for development only
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,}$")
COMMON_PASSWORDS = {"password", "password123", "1234567890", "qwertyuiop", "123456789012", "iloveyou12",
                    "admin12345", "letmein123", "welcome123", "polypilot1", "codeforces1"}


def secret_key() -> str:
    key = get_settings().AUTH_SECRET_KEY
    return key if key else _dev_secret


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_email(email: str) -> Optional[str]:
    return None if EMAIL_RE.match(email) and len(email) <= 254 else "Enter a valid email address"


def validate_password(password: str, email: str = "") -> Optional[str]:
    if len(password) < 10:
        return "Password must be at least 10 characters"
    if len(password) > 128:
        return "Password must be at most 128 characters"
    if len(set(password)) < 4:
        return "Password is too repetitive"
    if password.lower() in COMMON_PASSWORDS:
        return "Password is too common"
    local = email.split("@")[0].lower()
    if len(local) >= 4 and local in password.lower():
        return "Password must not contain your email name"
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: Optional[str], password: str) -> bool:
    """Constant-ish time: verifies against a dummy hash when the user does not exist."""
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return False


def new_session_token() -> Tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_for(token_hash: str) -> str:
    return hmac.new(secret_key().encode(), f"csrf:{token_hash}".encode(), hashlib.sha256).hexdigest()


def csrf_valid(token_hash: str, presented: Optional[str]) -> bool:
    return bool(presented) and hmac.compare_digest(csrf_for(token_hash), presented)


class RateLimiter:
    """Sliding-window counter. In-memory: limits apply per backend process."""

    def __init__(self):
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_sec: float, record: bool = True) -> bool:
        """Return True if allowed. When record=False, only checks."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - window_sec:
                q.popleft()
            if len(q) >= limit:
                return False
            if record:
                q.append(now)
            if len(self._hits) > 50000:   # bound memory
                for k in list(self._hits)[:10000]:
                    if not self._hits[k]:
                        del self._hits[k]
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
