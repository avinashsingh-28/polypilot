"""AI provider status for the current user (no keys are ever returned)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.services.ai import SUPPORTED_PROVIDERS, calls_today

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/status")
def ai_status(db: Session = Depends(get_db), user: User = Depends(require_user)):
    s = get_settings()
    return {"provider": s.AI_PROVIDER, "model": s.AI_MODEL, "configured": bool(s.GEMINI_API_KEY),
            "supported_providers": list(SUPPORTED_PROVIDERS), "timeout_sec": s.AI_TIMEOUT_SEC,
            "max_output_tokens": s.AI_MAX_OUTPUT_TOKENS, "daily_limit": s.AI_MAX_CALLS_PER_USER_PER_DAY,
            "calls_last_24h": calls_today(db, user.id),
            "note": "Provider and key are configured server-side in backend/.env; they cannot be set from the browser."}
