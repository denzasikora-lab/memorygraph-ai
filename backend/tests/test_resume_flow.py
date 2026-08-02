from fastapi.testclient import TestClient

from app.main import app


def test_memory_survives_stop_restart_and_resume() -> None:
    with TestClient(app) as client:
        session = client.post("/api/sessions", json={"title": "Release plan"}).json()
        task = client.post(f"/api/sessions/{session['id']}/tasks", json={"prompt": "Plan a safe rollout"}).json()
        first = client.post(f"/api/tasks/{task['id']}/run-step")
        assert first.status_code == 200
        assert first.json()["event"]["agent_name"] == "orchestrator"
        assert client.post(f"/api/tasks/{task['id']}/stop").json()["state"] == "stopped"
        retrieval = client.get(f"/api/sessions/{session['id']}/memories/search", params={"query": "safe rollout"}).json()
        assert retrieval["results"] and retrieval["results"][0]["score"] <= 1

    # A fresh ASGI client represents an app process restart; state comes from the persisted database.
    with TestClient(app) as restarted:
        assert restarted.post(f"/api/tasks/{task['id']}/resume").json()["next_agent_index"] == 1
        resumed = restarted.post(f"/api/tasks/{task['id']}/run-step").json()
        assert resumed["event"]["agent_name"] == "planner"
        dashboard = restarted.get(f"/api/sessions/{session['id']}/dashboard").json()
        assert [event["agent_name"] for event in dashboard["events"]][:2] == ["planner", "orchestrator"]
        assert dashboard["graph"]["edges"]


def test_request_validation_rejects_empty_prompt() -> None:
    with TestClient(app) as client:
        session = client.post("/api/sessions", json={"title": "Validation"}).json()
        response = client.post(f"/api/sessions/{session['id']}/tasks", json={"prompt": ""})
        assert response.status_code == 422
