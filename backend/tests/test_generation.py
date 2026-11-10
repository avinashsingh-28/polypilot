import uuid
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.models.problem import Problem
from app.models.generation import GenerationJob
from app.models.artifact import ProblemArtifact


def test_generate_without_api_key(client: TestClient, db_session):
    problem = Problem(
        title="Test Problem",
        slug=f"test-slug-{uuid.uuid4().hex[:6]}",
        idea="Test idea",
    )
    db_session.add(problem)
    db_session.commit()
    db_session.refresh(problem)

    with patch("app.api.routes.generation.get_settings") as mock_settings:
        mock_settings.return_value.GEMINI_API_KEY = ""
        response = client.post(f"/api/v1/problems/{problem.id}/generate")
        assert response.status_code == 503
        assert "GEMINI_API_KEY" in response.json()["detail"]


def test_generation_status_not_found(client: TestClient, db_session):
    problem = Problem(
        title="Test Problem",
        slug=f"test-slug-{uuid.uuid4().hex[:6]}",
    )
    db_session.add(problem)
    db_session.commit()
    db_session.refresh(problem)

    response = client.get(f"/api/v1/problems/{problem.id}/generation-status")
    assert response.status_code == 404


def test_generate_creates_job_and_returns_status(client: TestClient, db_session):
    problem = Problem(
        title="Knapsack Problem",
        slug=f"knapsack-{uuid.uuid4().hex[:6]}",
        idea="Given items with weights and values, find max value.",
    )
    db_session.add(problem)
    db_session.commit()
    db_session.refresh(problem)

    with patch("app.api.routes.generation.get_settings") as mock_settings, \
         patch("app.api.routes.generation.run_generation_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_settings.return_value.GEMINI_API_KEY = "dummy-test-key"

        response = client.post(f"/api/v1/problems/{problem.id}/generate")
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["problem_id"] == str(problem.id)

        # Status check
        status_resp = client.get(f"/api/v1/problems/{problem.id}/generation-status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["status"] == "running"
        assert status_data["total_steps"] == 7


def test_regenerate_step_invalid_step(client: TestClient, db_session):
    problem = Problem(
        title="Test Problem",
        slug=f"test-slug-{uuid.uuid4().hex[:6]}",
    )
    db_session.add(problem)
    db_session.commit()
    db_session.refresh(problem)

    with patch("app.api.routes.generation.get_settings") as mock_settings:
        mock_settings.return_value.GEMINI_API_KEY = "dummy-key"
        response = client.post(
            f"/api/v1/problems/{problem.id}/regenerate-step",
            json={"step": "invalid_step_name"}
        )
        assert response.status_code == 422
