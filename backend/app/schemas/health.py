from typing import Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str


class DbHealthResponse(BaseModel):
    status: str
    database: str
    reachable: bool
    latency_ms: Optional[float] = None
    detail: Optional[str] = None
