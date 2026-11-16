"""
Admin CLI (run on the server, never exposed over HTTP).

  python -m app.cli create-user --email you@example.com      # prompts for the password
  python -m app.cli claim-problems --email you@example.com   # assign legacy (unowned) problems
  python -m app.cli prune [--days 90] [--dry-run]            # data retention
"""
import argparse
import getpass
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_

from app.core.security import hash_password, normalize_email, validate_email, validate_password
from app.db.session import SessionLocal
from app.models.polygon import PolygonOperation
from app.models.problem import Problem
from app.models.user import AIUsage, User, UserSession, WorkerHeartbeat


def create_user(email: str) -> int:
    email = normalize_email(email)
    if validate_email(email):
        print("Invalid email")
        return 2
    pw = getpass.getpass("Password: ")
    if pw != getpass.getpass("Repeat password: "):
        print("Passwords do not match")
        return 2
    err = validate_password(pw, email)
    if err:
        print(err)
        return 2
    with SessionLocal() as db:
        if db.query(User).filter_by(email=email).first():
            print("User already exists")
            return 1
        db.add(User(email=email, password_hash=hash_password(pw)))
        db.commit()
    print(f"Created {email}")
    return 0


def claim_problems(email: str) -> int:
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=normalize_email(email)).first()
        if not user:
            print("No such user; register first")
            return 1
        n = db.query(Problem).filter(Problem.owner_id.is_(None)).update({"owner_id": user.id})
        db.commit()
    print(f"Assigned {n} unowned problems to {email}")
    return 0


def prune(days: int, dry_run: bool) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        q = {
            "expired/revoked sessions": db.query(UserSession).filter(or_(UserSession.expires_at < now,
                                                                         UserSession.revoked_at.isnot(None))),
            f"polygon request logs older than {days}d": db.query(PolygonOperation).filter(PolygonOperation.created_at < cutoff),
            f"AI usage rows older than {days}d": db.query(AIUsage).filter(AIUsage.created_at < cutoff),
            "worker heartbeats older than 1d": db.query(WorkerHeartbeat).filter(
                WorkerHeartbeat.last_seen_at < now - timedelta(days=1)),
        }
        for label, query in q.items():
            n = query.count()
            if not dry_run:
                query.delete(synchronize_session=False)
            print(f"{'would delete' if dry_run else 'deleted'} {n} {label}")
        if not dry_run:
            db.commit()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("create-user", "claim-problems"):
        sp = sub.add_parser(name)
        sp.add_argument("--email", required=True)
    sp = sub.add_parser("prune")
    sp.add_argument("--days", type=int, default=90)
    sp.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "create-user":
        return create_user(a.email)
    if a.cmd == "claim-problems":
        return claim_problems(a.email)
    return prune(a.days, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
