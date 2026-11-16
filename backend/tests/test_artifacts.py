from fastapi.testclient import TestClient


def test_create_and_version_artifacts(client: TestClient):
    # 1. Create a problem
    prob_res = client.post("/api/v1/problems", json={"title": "Artifacts Test Problem"})
    problem_id = prob_res.json()["id"]

    # 2. Add first version of statement artifact
    art1_payload = {
        "artifact_type": "statement",
        "name": "statement.tex",
        "content": "\\begin{problem}{Artifacts Test}",
        "language": "latex"
    }
    art1_res = client.post(f"/api/v1/problems/{problem_id}/artifacts", json=art1_payload)
    assert art1_res.status_code == 201
    art1_data = art1_res.json()
    assert art1_data["version"] == 1
    assert art1_data["artifact_type"] == "statement"
    artifact1_id = art1_data["id"]

    # 3. Add second version of statement artifact
    art2_payload = {
        "artifact_type": "statement",
        "name": "statement.tex",
        "content": "\\begin{problem}{Artifacts Test Revised}",
        "language": "latex"
    }
    art2_res = client.post(f"/api/v1/problems/{problem_id}/artifacts", json=art2_payload)
    assert art2_res.status_code == 201
    assert art2_res.json()["version"] == 2

    # 4. List artifacts for problem
    list_res = client.get(f"/api/v1/problems/{problem_id}/artifacts")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 2

    # 5. Get specific artifact
    get_art_res = client.get(f"/api/v1/artifacts/{artifact1_id}")
    assert get_art_res.status_code == 200
    assert get_art_res.json()["content"] == art1_payload["content"]

    # 6. Update artifact content (bumps version)
    patch_res = client.patch(
        f"/api/v1/artifacts/{artifact1_id}",
        json={"content": "Updated content"}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["content"] == "Updated content"
    assert patch_res.json()["version"] == 2


def test_cascade_delete_artifacts(client: TestClient):
    prob_res = client.post("/api/v1/problems", json={"title": "Cascade Delete Problem"})
    problem_id = prob_res.json()["id"]

    art_res = client.post(
        f"/api/v1/problems/{problem_id}/artifacts",
        json={"artifact_type": "validator", "content": "#include \"testlib.h\""}
    )
    artifact_id = art_res.json()["id"]

    # Delete problem
    del_res = client.delete(f"/api/v1/problems/{problem_id}")
    assert del_res.status_code == 204

    # The artifact should also be deleted
    art_get_res = client.get(f"/api/v1/artifacts/{artifact_id}")
    assert art_get_res.status_code == 404
