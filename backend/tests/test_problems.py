import uuid
from fastapi.testclient import TestClient


def test_create_and_get_problem(client: TestClient):
    payload = {
        "title": "Bitwise OR Partition",
        "idea": "Partition array such that OR sum of each segment is even.",
        "algorithm": "Dynamic Programming",
        "difficulty": "Div. 2 B",
        "time_limit_seconds": 1.5,
        "memory_limit_mb": 512
    }
    create_res = client.post("/api/v1/problems", json=payload)
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["title"] == payload["title"]
    assert created_data["slug"] == "bitwise-or-partition"
    assert created_data["status"] == "draft"
    assert float(created_data["time_limit_seconds"]) == 1.5
    assert created_data["memory_limit_mb"] == 512
    problem_id = created_data["id"]

    # Retrieve by ID
    get_res = client.get(f"/api/v1/problems/{problem_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == problem_id


def test_slug_auto_deduplication(client: TestClient):
    payload1 = {"title": "Graph Diameter Query"}
    payload2 = {"title": "Graph Diameter Query"}

    res1 = client.post("/api/v1/problems", json=payload1)
    res2 = client.post("/api/v1/problems", json=payload2)

    assert res1.status_code == 201
    assert res2.status_code == 201
    slug1 = res1.json()["slug"]
    slug2 = res2.json()["slug"]
    assert slug1 != slug2
    assert slug2.startswith("graph-diameter-query-")


def test_list_problems_pagination(client: TestClient):
    for i in range(5):
        client.post("/api/v1/problems", json={"title": f"Test Problem {i}"})

    list_res = client.get("/api/v1/problems?limit=3&offset=0")
    assert list_res.status_code == 200
    data = list_res.json()
    assert len(data["items"]) == 3
    assert data["total"] >= 5
    assert data["limit"] == 3
    assert data["offset"] == 0


def test_update_problem(client: TestClient):
    create_res = client.post("/api/v1/problems", json={"title": "Original Problem"})
    problem_id = create_res.json()["id"]

    update_res = client.patch(
        f"/api/v1/problems/{problem_id}",
        json={
            "title": "Updated Title",
            "difficulty": "Div. 1 A",
            "memory_limit_mb": 1024
        }
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["title"] == "Updated Title"
    assert updated["difficulty"] == "Div. 1 A"
    assert updated["memory_limit_mb"] == 1024


def test_update_slug_conflict(client: TestClient):
    res1 = client.post("/api/v1/problems", json={"title": "Unique Slug One", "slug": "slug-one"})
    res2 = client.post("/api/v1/problems", json={"title": "Unique Slug Two", "slug": "slug-two"})
    p2_id = res2.json()["id"]

    # Attempt to change p2's slug to "slug-one"
    conflict_res = client.patch(f"/api/v1/problems/{p2_id}", json={"slug": "slug-one"})
    assert conflict_res.status_code == 409


def test_delete_problem(client: TestClient):
    create_res = client.post("/api/v1/problems", json={"title": "Problem To Delete"})
    problem_id = create_res.json()["id"]

    del_res = client.delete(f"/api/v1/problems/{problem_id}")
    assert del_res.status_code == 204

    # Subsequent GET should return 404
    get_res = client.get(f"/api/v1/problems/{problem_id}")
    assert get_res.status_code == 404


def test_invalid_uuid(client: TestClient):
    get_res = client.get("/api/v1/problems/not-a-valid-uuid")
    assert get_res.status_code == 422


def test_missing_problem_404(client: TestClient):
    random_id = str(uuid.uuid4())
    get_res = client.get(f"/api/v1/problems/{random_id}")
    assert get_res.status_code == 404
