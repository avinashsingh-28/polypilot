import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.artifact import ProblemArtifact
from app.schemas.artifact import ArtifactUpdate, ArtifactResponse

router = APIRouter(prefix="/artifacts", tags=["Artifacts"])


@router.get("/{artifact_id}", response_model=ArtifactResponse)
def get_artifact(
    artifact_id: uuid.UUID,
    db: Session = Depends(get_db)
) -> ProblemArtifact:
    """Retrieve a specific artifact by its UUID."""
    artifact = db.get(ProblemArtifact, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact with ID {artifact_id} not found"
        )
    return artifact


@router.patch("/{artifact_id}", response_model=ArtifactResponse)
def update_artifact(
    artifact_id: uuid.UUID,
    payload: ArtifactUpdate,
    db: Session = Depends(get_db)
) -> ProblemArtifact:
    """
    Update artifact content and increment its version number.
    Ensures safe persistence in PostgreSQL.
    """
    artifact = db.get(ProblemArtifact, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact with ID {artifact_id} not found"
        )

    # Apply updates and bump version
    artifact.content = payload.content
    if payload.name is not None:
        artifact.name = payload.name
    if payload.language is not None:
        artifact.language = payload.language
    artifact.version += 1

    db.commit()
    db.refresh(artifact)
    return artifact
