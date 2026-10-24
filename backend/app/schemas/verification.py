import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class VerificationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problem_id: uuid.UUID
    status: str
    summary: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
