import uuid
import re
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator, ConfigDict


def generate_slug_from_title(title: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', title).strip('-').lower()
    return slug[:100] or f"problem-{uuid.uuid4().hex[:8]}"


class ProblemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = Field(None, max_length=255)
    idea: Optional[str] = None
    algorithm: Optional[str] = Field(None, max_length=255)
    constraints_text: Optional[str] = None
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    time_limit_seconds: Optional[Decimal] = Field(default=Decimal("2.0"), ge=0.1, le=60.0)
    memory_limit_mb: Optional[int] = Field(default=256, ge=16, le=4096)
    difficulty: Optional[str] = Field(None, max_length=100)
    language: str = Field(default="cpp", max_length=50)


class ProblemCreate(ProblemBase):
    @model_validator(mode="after")
    def populate_slug_if_missing(self) -> "ProblemCreate":
        if not self.slug and self.title:
            self.slug = generate_slug_from_title(self.title)
        return self


class ProblemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, max_length=255)
    idea: Optional[str] = None
    algorithm: Optional[str] = Field(None, max_length=255)
    constraints_text: Optional[str] = None
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    time_limit_seconds: Optional[Decimal] = Field(None, ge=0.1, le=60.0)
    memory_limit_mb: Optional[int] = Field(None, ge=16, le=4096)
    difficulty: Optional[str] = Field(None, max_length=100)
    language: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=50)


class ProblemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    idea: Optional[str] = None
    algorithm: Optional[str] = None
    constraints_text: Optional[str] = None
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    time_limit_seconds: Optional[Decimal] = None
    memory_limit_mb: Optional[int] = None
    difficulty: Optional[str] = None
    language: str
    status: str
    created_at: datetime
    updated_at: datetime


class ProblemListResponse(BaseModel):
    items: List[ProblemResponse]
    total: int
    limit: int
    offset: int
