import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import require_user
from app.models.user import User
from app.models.problem import Problem
from app.models.artifact import ProblemArtifact
from app.models.verification import VerificationRun
from app.schemas.problem import (
    ProblemCreate,
    ProblemUpdate,
    ProblemResponse,
    ProblemListResponse,
    generate_slug_from_title
)
from app.schemas.artifact import ArtifactCreate, ArtifactResponse
from app.schemas.verification import VerificationRunResponse

router = APIRouter(prefix="/problems", tags=["Problems"])


@router.get("", response_model=ProblemListResponse)
def list_problems(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> ProblemListResponse:
    """List the current user's problems ordered by most recently updated, with pagination."""
    total_query = select(func.count(Problem.id)).where(Problem.owner_id == user.id)
    total = db.scalar(total_query) or 0

    stmt = (
        select(Problem)
        .where(Problem.owner_id == user.id)
        .order_by(Problem.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(db.scalars(stmt).all())

    return ProblemListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset
    )


@router.post("", response_model=ProblemResponse, status_code=status.HTTP_201_CREATED)
def create_problem(
    payload: ProblemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Problem:
    """Create a new problem draft with a unique slug."""
    # Ensure slug uniqueness
    base_slug = payload.slug or generate_slug_from_title(payload.title)
    existing = db.scalar(select(Problem).where(Problem.slug == base_slug))
    if existing:
        base_slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    problem = Problem(
        owner_id=user.id,
        title=payload.title,
        slug=base_slug,
        idea=payload.idea,
        algorithm=payload.algorithm,
        constraints_text=payload.constraints_text,
        input_format=payload.input_format,
        output_format=payload.output_format,
        time_limit_seconds=payload.time_limit_seconds,
        memory_limit_mb=payload.memory_limit_mb,
        difficulty=payload.difficulty,
        language=payload.language,
        status="draft"
    )

    db.add(problem)
    db.commit()
    db.refresh(problem)
    return problem


@router.get("/{problem_id}", response_model=ProblemResponse)
def get_problem(
    problem_id: uuid.UUID,
    db: Session = Depends(get_db)
) -> Problem:
    """Retrieve problem details by ID."""
    problem = db.get(Problem, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem with ID {problem_id} not found"
        )
    return problem


@router.patch("/{problem_id}", response_model=ProblemResponse)
def update_problem(
    problem_id: uuid.UUID,
    payload: ProblemUpdate,
    db: Session = Depends(get_db)
) -> Problem:
    """Update editable fields of a problem."""
    problem = db.get(Problem, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem with ID {problem_id} not found"
        )

    update_data = payload.model_dump(exclude_unset=True)

    # Check slug conflict if slug is being updated
    if "slug" in update_data and update_data["slug"] != problem.slug:
        existing = db.scalar(
            select(Problem).where(
                Problem.slug == update_data["slug"],
                Problem.id != problem_id
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Problem slug '{update_data['slug']}' is already in use."
            )

    for field, value in update_data.items():
        setattr(problem, field, value)

    db.commit()
    db.refresh(problem)
    return problem


@router.delete("/{problem_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_problem(
    problem_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Delete a problem and all associated artifacts/runs (cascade delete)."""
    problem = db.get(Problem, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem with ID {problem_id} not found"
        )
    db.delete(problem)
    db.commit()
    return None


@router.get("/{problem_id}/artifacts", response_model=List[ArtifactResponse])
def list_problem_artifacts(
    problem_id: uuid.UUID,
    db: Session = Depends(get_db)
) -> List[ProblemArtifact]:
    """List all artifacts associated with a problem."""
    problem = db.get(Problem, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem with ID {problem_id} not found"
        )

    stmt = (
        select(ProblemArtifact)
        .where(ProblemArtifact.problem_id == problem_id)
        .order_by(ProblemArtifact.created_at.desc(), ProblemArtifact.version.desc())
    )
    return list(db.scalars(stmt).all())


@router.post("/{problem_id}/artifacts", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
def create_problem_artifact(
    problem_id: uuid.UUID,
    payload: ArtifactCreate,
    db: Session = Depends(get_db)
) -> ProblemArtifact:
    """Create or save a new artifact for a problem, calculating next version."""
    problem = db.get(Problem, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem with ID {problem_id} not found"
        )

    # Find highest existing version for this artifact_type on this problem
    max_ver = db.scalar(
        select(func.max(ProblemArtifact.version)).where(
            ProblemArtifact.problem_id == problem_id,
            ProblemArtifact.artifact_type == payload.artifact_type
        )
    )
    next_ver = (max_ver or 0) + 1

    artifact = ProblemArtifact(
        problem_id=problem_id,
        artifact_type=payload.artifact_type,
        name=payload.name,
        content=payload.content,
        language=payload.language,
        version=next_ver
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


@router.get("/{problem_id}/verification-runs", response_model=List[VerificationRunResponse])
def list_problem_verification_runs(
    problem_id: uuid.UUID,
    db: Session = Depends(get_db)
) -> List[VerificationRun]:
    """List verification runs for a problem."""
    problem = db.get(Problem, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem with ID {problem_id} not found"
        )

    stmt = (
        select(VerificationRun)
        .where(VerificationRun.problem_id == problem_id)
        .order_by(VerificationRun.created_at.desc())
    )
    return list(db.scalars(stmt).all())
