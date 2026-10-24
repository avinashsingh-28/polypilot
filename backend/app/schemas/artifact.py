import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ArtifactCreate(BaseModel):
    artifact_type: str = Field(..., min_length=1, max_length=100)
    name: Optional[str] = Field(None, max_length=255)
    content: str = Field(default="")
    language: Optional[str] = Field(None, max_length=50)


class ArtifactUpdate(BaseModel):
    content: str
    name: Optional[str] = Field(None, max_length=255)
    language: Optional[str] = Field(None, max_length=50)


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problem_id: uuid.UUID
    artifact_type: str
    name: Optional[str] = None
    content: str
    language: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime
