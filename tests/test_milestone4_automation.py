"""Tests for Milestone 4 Workflow Automation, Dashboard Stats, API Authentication, and Webhooks."""

from __future__ import annotations

from unittest.mock import patch

from bizpilot.extensions import db
from bizpilot.models import User, WorkflowJob, WorkflowTemplate

from bizpilot.services.scheduler import execute_workflow_job, sync_templates_to_scheduler
from bizpilot.services.webhook import trigger_webhook


def test_api_key_authentication(client):
    """Verify POST /api/workflows/trigger requires API key or active session."""
    # 1. No auth or API key -> 401 Unauthorized
    res = client.post("/api/workflows/trigger", json={"query": "Test question"})
    assert res.status_code == 401
    assert res.get_json()["success"] is False

    # 2. Valid API key -> 200 OK
    res_valid = client.post(
        "/api/workflows/trigger",
        json={"query": "Automated restock check"},
        headers={"X-API-Key": "test-api-key"},
    )
    assert res_valid.status_code == 200
    payload = res_valid.get_json()
    assert payload["success"] is True
    assert "job_id" in payload
    assert payload["status"] == "pending"


def test_workflow_template_crud(app, client, auth):
    """Test creating, listing, and deleting workflow templates."""
    auth.login()

    # Create Template
    create_res = client.post(
        "/api/workflows/templates",
        json={
            "name": "Daily Stock Audit",
            "description": "Checks low stock items every morning",
            "schedule": "0 9 * * *",
            "parameters": {"query": "Check low inventory products"},
        },
    )
    assert create_res.status_code == 201
    template_data = create_res.get_json()["template"]
    assert template_data["name"] == "Daily Stock Audit"

    # List Templates
    list_res = client.get("/api/workflows/templates")
    assert list_res.status_code == 200
    templates = list_res.get_json()["templates"]
    assert len(templates) == 1
    assert templates[0]["name"] == "Daily Stock Audit"

    # Delete Template
    del_res = client.delete(f"/api/workflows/templates/{template_data['id']}")
    assert del_res.status_code == 200
    assert del_res.get_json()["success"] is True


def test_workflow_job_trigger_and_status(app, client, auth):
    """Test triggering a job and querying its status."""
    auth.login()

    # Trigger job
    trigger_res = client.post(
        "/api/workflows/trigger",
        json={"query": "Which products need restock?"},
        headers={"X-API-Key": "test-api-key"},
    )
    assert trigger_res.status_code == 200
    job_id = trigger_res.get_json()["job_id"]

    # Check job status endpoint
    status_res = client.get(
        f"/api/workflows/jobs/{job_id}",
        headers={"X-API-Key": "test-api-key"},
    )
    assert status_res.status_code == 200
    job_data = status_res.get_json()["job"]
    assert job_data["job_id"] == job_id
    assert job_data["status"] in ("pending", "running", "completed")


def test_dashboard_stats_endpoint(client, auth):
    """Test dashboard stats endpoint returns aggregated metrics."""
    auth.login()
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["success"] is True
    assert "summary" in payload
    assert "recent_jobs" in payload
    assert "agent_latencies" in payload
    assert "latest_steps" in payload


def test_background_job_execution(app):
    """Test synchronous execution of a WorkflowJob worker in app context."""
    with app.app_context():
        user = User(username="jobrunner", email="runner@example.com", password_hash="hash")
        db.session.add(user)
        db.session.commit()

        job = WorkflowJob(
            job_id="test-job-uuid-12345",
            user_id=user.id,
            status="pending",
            progress=0,
            result={},
            trigger_source="test",
        )
        db.session.add(job)
        db.session.commit()
        job_db_id = job.id

        execute_workflow_job(job_db_id, app, query="Test performance query")

        updated_job = db.session.get(WorkflowJob, job_db_id)
        assert updated_job.status in ("completed", "failed")
        assert updated_job.progress == 100
        assert updated_job.execution_time_ms >= 0


def test_webhook_dispatch(app):
    """Test webhook delivery logic with a mocked HTTP POST response."""
    with app.app_context():
        user = User(username="webhookuser", email="webhook@example.com", password_hash="hash")
        db.session.add(user)
        db.session.commit()

        job = WorkflowJob(
            job_id="test-webhook-job-123",
            user_id=user.id,
            status="completed",
            progress=100,
            result={"final_response": "Restock recommended."},
            webhook_url="https://example.com/webhook",
        )

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            success = trigger_webhook(job)
            assert success is True
            assert job.webhook_status == "success_200"
            mock_post.assert_called_once()


def test_scheduler_template_sync(app):
    """Test syncing templates to APScheduler."""
    with app.app_context():
        user = User(username="syncuser", email="sync@example.com", password_hash="hash")
        db.session.add(user)
        db.session.commit()

        template = WorkflowTemplate(
            user_id=user.id,
            name="Scheduled Test",
            schedule="every_5_minutes",
            parameters={"query": "Run scheduled check"},
            is_active=True,
        )
        db.session.add(template)
        db.session.commit()

        sync_templates_to_scheduler(app)

