"""
Authentication / authorization dependencies.

`require_user` is applied to the whole /api/v1 router (except /auth). `enforce_ownership`
is applied with it and checks every route that addresses a problem or an artifact by id,
so ownership is enforced centrally on the backend for all existing and future routes that
use the `problem_id` / `artifact_id` path parameter names.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import csrf_valid, hash_token
from app.db.session import get_db
from app.models.artifact import ProblemArtifact
from app.models.problem import Problem
from app.models.user import User, UserSession

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
NOT_FOUND = "Not found"


def _now():
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def load_session(db: Session, token: Optional[str]) -> Optional[UserSession]:
    if not token or len(token) > 200:
        return None
    s = get_settings()
    sess = db.query(UserSession).filter_by(token_hash=hash_token(token)).first()
    if not sess or sess.revoked_at is not None:
        return None
    now = _now()
    if _aware(sess.expires_at) <= now or _aware(sess.last_seen_at) + timedelta(minutes=s.SESSION_IDLE_TIMEOUT_MIN) <= now:
        return None
    return sess


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    s = get_settings()
    sess = load_session(db, request.cookies.get(s.SESSION_COOKIE_NAME))
    if sess is None:
        raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Session"})
    user = db.get(User, sess.user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Not authenticated")
    if request.method in UNSAFE and not csrf_valid(sess.token_hash, request.headers.get("X-CSRF-Token")):
        raise HTTPException(403, "CSRF token missing or invalid")
    now = _now()
    if (now - _aware(sess.last_seen_at)).total_seconds() > 300:   # rolling idle window, throttled writes
        sess.last_seen_at = now
        db.commit()
    request.state.user_id = str(user.id)
    return user


def owned_problem(db: Session, problem_id, user: User) -> Problem:
    try:
        pid = problem_id if isinstance(problem_id, uuid.UUID) else uuid.UUID(str(problem_id))
    except ValueError:
        raise HTTPException(404, NOT_FOUND)
    p = db.get(Problem, pid)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, NOT_FOUND)   # same response as "does not exist": no enumeration
    return p


def enforce_ownership(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)) -> None:
    params = request.path_params
    if "problem_id" in params:
        try:
            uuid.UUID(str(params["problem_id"]))
        except ValueError:
            return            # malformed id: let route validation return 422 (nothing is accessed)
        owned_problem(db, params["problem_id"], user)
    if "artifact_id" in params:
        try:
            aid = uuid.UUID(str(params["artifact_id"]))
        except ValueError:
            return
        art = db.get(ProblemArtifact, aid)
        if art is None:
            raise HTTPException(404, NOT_FOUND)
        owned_problem(db, art.problem_id, user)
