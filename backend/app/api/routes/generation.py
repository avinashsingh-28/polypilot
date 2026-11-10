"""
Generation API routes.

POST /problems/{problem_id}/generate         — start a generation job
GET  /problems/{problem_id}/generation-status — poll job progress
POST /problems/{problem_id}/regenerate-step  — regenerate a single artifact step
"""
import asyncio
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.models.problem import Problem
from app.models.generation import GenerationJob
from app.models.artifact import ProblemArtifact
from app.core.config import get_settings
from app.services.generation.pipeline import run_generation_pipeline, _now, _upsert_artifact
from app.services.generation.steps import (
    run_statement, run_reference_solution, run_brute_force,
    run_validator, run_generator, run_editorial,
)
from app.services.ai import get_ai_provider

router = APIRouter(prefix="/problems", tags=["generation"])
logger = logging.getLogger(__name__)

REGENERATABLE_STEPS = {
    "statement", "reference_solution", "brute_force",
    "validator", "generator", "editorial",
}


# ── Response schemas ──────────────────────────────────────────────────────────

class GenerationStatusResponse(BaseModel):
    job_id: str
    problem_id: str
    status: str
    current_step: int
    total_steps: int
    current_step_name: Optional[str]
    steps_log: list
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class StartGenerationResponse(BaseModel):
    job_id: str
    problem_id: str
    message: str


class RegenerateStepRequest(BaseModel):
    step: str  # one of REGENERATABLE_STEPS


class RegenerateStepResponse(BaseModel):
    artifact_type: str
    message: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_problem(db: Session, problem_id: uuid.UUID) -> Problem:
    problem = db.get(Problem, problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail=f"Problem {problem_id} not found")
    return problem


def _latest_job(db: Session, problem_id: uuid.UUID) -> Optional[GenerationJob]:
    return (
        db.query(GenerationJob)
        .filter(GenerationJob.problem_id == problem_id)
        .order_by(GenerationJob.created_at.desc())
        .first()
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{problem_id}/generate", response_model=StartGenerationResponse, status_code=202)
async def start_generation(
    problem_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start the AI generation pipeline for a problem."""
    settings = get_settings()

    # Guard: check API key is configured
    if not getattr(settings, "GEMINI_API_KEY", ""):
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured. Add it to backend/.env to enable generation.",
        )

    problem = _require_problem(db, problem_id)

    # If there's already a running job, reject
    existing = _latest_job(db, problem_id)
    if existing and existing.status == "running":
        raise HTTPException(
            status_code=409,
            detail="A generation job is already running for this problem.",
        )

    # Create job record
    job = GenerationJob(
        problem_id=problem_id,
        status="running",
        current_step=0,
        total_steps=7,
        steps_log=[],
        started_at=_now(),
    )
    db.add(job)
    problem.status = "generating"
    db.commit()
    db.refresh(job)

    job_id = job.id

    # Launch the pipeline as a background asyncio task
    background_tasks.add_task(_run_pipeline_task, problem_id, job_id)

    return StartGenerationResponse(
        job_id=str(job_id),
        problem_id=str(problem_id),
        message="Generation started. Poll /generation-status for progress.",
    )


async def _run_pipeline_task(problem_id: uuid.UUID, job_id: uuid.UUID) -> None:
    """Wrapper so BackgroundTasks can call our async pipeline."""
    try:
        await run_generation_pipeline(problem_id, job_id)
    except Exception as exc:
        logger.exception("Unhandled error in pipeline task: %s", exc)


@router.get("/{problem_id}/generation-status", response_model=GenerationStatusResponse)
def get_generation_status(
    problem_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Poll the latest generation job status for a problem."""
    _require_problem(db, problem_id)
    job = _latest_job(db, problem_id)
    if not job:
        raise HTTPException(status_code=404, detail="No generation job found for this problem.")
    return GenerationStatusResponse(
        job_id=str(job.id),
        problem_id=str(problem_id),
        status=job.status,
        current_step=job.current_step,
        total_steps=job.total_steps,
        current_step_name=job.current_step_name,
        steps_log=job.steps_log or [],
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.post("/{problem_id}/regenerate-step", response_model=RegenerateStepResponse)
async def regenerate_step(
    problem_id: uuid.UUID,
    body: RegenerateStepRequest,
    db: Session = Depends(get_db),
):
    """Regenerate a single artifact step without re-running the full pipeline."""
    settings = get_settings()
    if not getattr(settings, "GEMINI_API_KEY", ""):
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured.")

    if body.step not in REGENERATABLE_STEPS:
        raise HTTPException(
            status_code=422,
            detail=f"Step must be one of: {', '.join(sorted(REGENERATABLE_STEPS))}",
        )

    problem = _require_problem(db, problem_id)

    # Load spec artifact (required for all steps except specification itself)
    spec_artifact = (
        db.query(ProblemArtifact)
        .filter_by(problem_id=problem_id, artifact_type="specification")
        .first()
    )
    import json
    spec: dict = {}
    if spec_artifact and spec_artifact.content:
        try:
            spec = json.loads(spec_artifact.content)
        except json.JSONDecodeError:
            pass

    ai = get_ai_provider(settings)
    step_map = {
        "statement": run_statement,
        "reference_solution": run_reference_solution,
        "brute_force": run_brute_force,
        "validator": run_validator,
        "generator": run_generator,
        "editorial": run_editorial,
    }

    try:
        result = await step_map[body.step](ai, problem, spec)
        _upsert_artifact(db, problem_id, body.step, result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Regeneration failed: {exc}")

    return RegenerateStepResponse(
        artifact_type=body.step,
        message=f"Step '{body.step}' regenerated successfully.",
    )

