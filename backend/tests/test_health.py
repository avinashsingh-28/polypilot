from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data


def test_db_health_check(client: TestClient):
    response = client.get("/health/db")
    # Response may be 200 (if test db reachable) or 503 (if connection fails)
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "reachable" in data
