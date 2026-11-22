"""
Generation pipeline — orchestrates the 7 AI steps for one problem.
Runs as an asyncio background task; persists progress to PostgreSQL after each step.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.generation import GenerationJob
from app.models.problem import Problem
from app.models.artifact import ProblemArtifact
from app.services.ai.base import AIProvider
from app.services.ai import resolve_provider
from app.services.generation.steps import (
    run_specification,
    run_statement,
    run_reference_solution,
    run_brute_force,
    run_validator,
    run_generator,
    run_editorial,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)

STEPS = [
    ("specification",       "Building Specification"),
    ("statement",           "Writing Problem Statement"),
    ("reference_solution",  "Generating Reference Solution"),
    ("brute_force",         "Generating Brute-Force Solution"),
    ("validator",           "Writing Testlib Validator"),
    ("generator",           "Writing Test Generator"),
    ("editorial",           "Writing Editorial"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_job(db: Session, problem_id: uuid.UUID) -> GenerationJob:
    """Create a new generation job row (or reset an existing pending one)."""
    job = GenerationJob(
        problem_id=problem_id,
        status="running",
        current_step=0,
        total_steps=len(STEPS),
        steps_log=[],
        started_at=_now(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _upsert_artifact(db: Session, problem_id: uuid.UUID,
                     artifact_type: str, content: str) -> None:
    """Insert or replace a ProblemArtifact row."""
    existing = (
        db.query(ProblemArtifact)
        .filter_by(problem_id=problem_id, artifact_type=artifact_type)
        .first()
    )
    if existing:
        if existing.content != content:
            existing.version = (existing.version or 1) + 1   # lets Phase 4/5 detect changed artifacts
        existing.content = content
        existing.updated_at = _now()
    else:
        artifact = ProblemArtifact(
            problem_id=problem_id,
            artifact_type=artifact_type,
            content=content,
            version=1,
        )
        db.add(artifact)
    db.commit()


def _step_log_entry(step_index: int, step_key: str, step_name: str,
                    status: str, error: Optional[str] = None) -> dict:
    return {
        "step": step_index + 1,
        "key": step_key,
        "name": step_name,
        "status": status,
        "timestamp": _now().isoformat(),
        **({"error": error} if error else {}),
    }


async def run_generation_pipeline(problem_id: uuid.UUID, job_id: uuid.UUID) -> None:
    """
    Main pipeline coroutine.  Runs all steps sequentially and persists results.
    Designed to be called with asyncio.create_task().
    """
    settings = get_settings()

    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)
        problem = db.get(Problem, problem_id)
        if not job or not problem:
            logger.error("Job or problem not found: job=%s problem=%s", job_id, problem_id)
            return
        try:
            # The owner's selected provider + own key, else the server's provider.
            inner, daily_limit = resolve_provider(db, problem.owner_id, settings)
        except Exception as exc:
            logger.error("Failed to initialise AI provider: %s", type(exc).__name__)
            job.status = "failed"
            job.error_message = f"AI provider not available: {getattr(exc, 'message', None) or type(exc).__name__}"
            job.completed_at = _now()
            db.commit()
            return
        from app.services.ai import TrackedProvider
        ai: AIProvider = TrackedProvider(inner, SessionLocal, problem.owner_id, problem.id, "generation", daily_limit)

        spec: dict = {}
        steps_log = []

        step_fns = [
            run_specification,
            run_statement,
            run_reference_solution,
            run_brute_force,
            run_validator,
            run_generator,
            run_editorial,
        ]

        for idx, ((step_key, step_name), step_fn) in enumerate(zip(STEPS, step_fns)):
            # Update job: now running this step
            job.current_step = idx + 1
            job.current_step_name = step_name
            steps_log.append(_step_log_entry(idx, step_key, step_name, "running"))
            job.steps_log = list(steps_log)
            db.commit()

            try:
                result = await step_fn(ai, problem, spec)

                # Store spec for later steps
                if step_key == "specification":
                    spec = result  # dict
                    import json
                    _upsert_artifact(db, problem_id, "specification", json.dumps(result, indent=2))
                    # Also update problem title/algorithm from spec
                    problem.title = result.get("problem_name", problem.title)
                    problem.algorithm = result.get("intended_algorithm", problem.algorithm)
                    db.commit()
                else:
                    _upsert_artifact(db, problem_id, step_key, result)

                steps_log[-1] = _step_log_entry(idx, step_key, step_name, "completed")
                job.steps_log = list(steps_log)
                db.commit()
                logger.info("Step %d/%d completed: %s", idx + 1, len(STEPS), step_name)

            except Exception as exc:
                err_msg = getattr(exc, "message", None) or f"{type(exc).__name__}: {str(exc)[:300]}"
                logger.exception("Step %d failed (%s): %s", idx + 1, step_name, err_msg)
                steps_log[-1] = _step_log_entry(idx, step_key, step_name, "failed", err_msg)
                job.steps_log = list(steps_log)
                job.status = "failed"
                job.error_message = f"Step '{step_name}' failed: {err_msg}"
                job.completed_at = _now()
                problem.status = "failed"
                db.commit()
                return

        # All steps done
        job.status = "completed"
        job.current_step = len(STEPS)
        job.completed_at = _now()
        problem.status = "generated"
        db.commit()
        logger.info("Generation pipeline completed for problem %s", problem_id)

