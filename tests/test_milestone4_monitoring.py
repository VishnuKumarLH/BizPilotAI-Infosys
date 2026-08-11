from __future__ import annotations

from bizpilot.extensions import db
from bizpilot.models import AgentWorkflowRun


def test_health_endpoint_reports_safe_service_status(client):
    response = client.get("/api/health")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["services"]["database"] == "ok"
    assert "GEMINI_API_KEY" not in str(payload)
    assert "GROQ_API_KEY" not in str(payload)


def test_favicon_uses_the_existing_logo(client):
    response = client.get("/favicon.ico", follow_redirects=True)

    assert response.status_code == 200
    assert response.mimetype == "image/png"


def test_workflow_lifecycle_metrics_and_timeline(app, client, auth):
    auth.login()
    created = client.post(
        "/api/agent/run", json={"query": "Which products should I restock?"}
    ).get_json()

    with app.app_context():
        run = db.session.scalar(
            db.select(AgentWorkflowRun).where(
                AgentWorkflowRun.workflow_id == created["workflow_id"]
            )
        )
        assert run is not None
        statuses = [event["status"] for event in run.lifecycle_events_json]
        assert statuses[0] == "CREATED"
        assert "VALIDATING" in statuses
        assert statuses[-1] == "COMPLETED"

    metrics = client.get("/api/metrics").get_json()
    assert metrics["success"] is True
    assert metrics["metrics"]["workflows"]["total"] == 1
    assert metrics["metrics"]["workflows"]["completed"] == 1
    assert metrics["metrics"]["agents"]
    assert metrics["metrics"]["tools"]

    timeline = client.get(
        f"/api/workflows/{created['workflow_id']}/timeline"
    ).get_json()
    assert timeline["success"] is True
    assert any(item["type"] == "lifecycle" for item in timeline["timeline"])
    assert any(item["type"] == "agent" for item in timeline["timeline"])
    assert any(item["type"] == "tool" for item in timeline["timeline"])


def test_milestone4_detail_endpoints_enforce_ownership(client, auth):
    auth.login()
    created = client.post(
        "/api/agent/run", json={"query": "How is my business performing this month?"}
    ).get_json()
    assert client.get(f"/api/workflows/{created['workflow_id']}/agents").status_code == 200
    assert client.get(f"/api/workflows/{created['workflow_id']}/tools").status_code == 200

    auth.logout()
    auth.login("other@example.com", "password123")
    assert client.get(f"/api/workflows/{created['workflow_id']}/timeline").status_code == 404
    assert client.get(f"/api/workflows/{created['workflow_id']}/agents").status_code == 404
    assert client.get(f"/api/workflows/{created['workflow_id']}/tools").status_code == 404
