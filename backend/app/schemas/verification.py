import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class VerificationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problem_id: uuid.UUID
    test_type: str = "full"
    status: str
    summary: Optional[str] = None
    error_message: Optional[str] = None
    config_params: Optional[Dict[str, Any]] = None
    progress: Optional[Dict[str, Any]] = None
    cancel_requested: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class VerificationRunDetail(VerificationRunResponse):
    report: Optional[Dict[str, Any]] = None
    logs: Optional[str] = None


class VerificationRunCreate(BaseModel):
    test_type: str = Field(..., max_length=50)
    config: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(None, max_length=100, pattern=r"^[A-Za-z0-9_\-:.]+$")


class TestCaseCreate(BaseModel):
    input_data: str
    expected_output: Optional[str] = None
    test_type: str = Field("manual", pattern=r"^(manual|upload|invalid)$")
    filename: Optional[str] = Field(None, max_length=255)


class TestCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problem_id: uuid.UUID
    test_type: str
    input_preview: str
    input_bytes: int
    input_truncated: bool
    has_expected_output: bool
    is_valid: bool
    validation_status: str
    validation_feedback: Optional[str] = None
    generator_cmd: Optional[str] = None
    generation_meta: Optional[Dict[str, Any]] = None
    created_at: datetime


class TestCaseDetail(TestCaseResponse):
    input_data: str
    expected_output: Optional[str] = None


class CounterexampleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problem_id: uuid.UUID
    verification_run_id: Optional[uuid.UUID] = None
    kind: str
    input_data: str
    minimized_input: Optional[str] = None
    ref_output: str
    candidate_output: str
    seed: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime


class RepairCreate(BaseModel):
    counterexample_id: uuid.UUID
    artifact_id: Optional[uuid.UUID] = None
    source: Optional[str] = None
    language: Optional[str] = Field(None, max_length=20)


class RepairResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problem_id: uuid.UUID
    verification_run_id: Optional[uuid.UUID] = None
    counterexample_id: Optional[uuid.UUID] = None
    artifact_id: Optional[uuid.UUID] = None
    retest_run_id: Optional[uuid.UUID] = None
    language: str
    version: int
    suspected_bug: Optional[str] = None
    explanation: str
    original_code: str
    repaired_code: str
    status: str
    created_at: datetime


class SandboxStatus(BaseModel):
    available: bool
    mode: str
    image: str
    image_present: bool
    server_version: Optional[str] = None
    error: Optional[str] = None


class VerificationSummary(BaseModel):
    sandbox: Optional[SandboxStatus] = None
    latest_by_type: Dict[str, Optional[VerificationRunResponse]]
    active_runs: List[VerificationRunResponse]
    test_case_counts: Dict[str, int]
    counterexample_count: int
    ai_configured: bool
