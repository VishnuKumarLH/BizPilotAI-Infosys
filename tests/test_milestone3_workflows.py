from __future__ import annotations

import pytest

from bizpilot.extensions import db
from bizpilot.models import AgentExecutionLog, AgentMemory, AgentWorkflowRun, ToolCallLog


@pytest.mark.parametrize(
    ("query", "intent", "required_key"),
    [
        ("Which products should I restock?", "inventory", "low_stock_tool"),
        (
            "How is my business performing this month?",
            "business_performance",
            "sales_summary_tool",
        ),
        (
            "What are customers complaining about?",
            "feedback",
            "feedback_category_tool",
        ),
    ],
)
def test_main_business_workflows_persist_state(
    app, client, auth, query, intent, required_key
):
    auth.login()
    response = client.post("/api/agent/run", json={"query": query})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["intent"] == intent
    assert payload["status"] == "completed"
    assert required_key in payload["tools_used"]
    assert payload["agents_used"] == [
        "planning_agent",
        "research_agent",
        "analysis_decision_agent",
        "response_agent",
    ]
    assert payload["final_response"]
    with app.app_context():
        run = db.session.scalar(
            db.select(AgentWorkflowRun).where(
                AgentWorkflowRun.workflow_id == payload["workflow_id"]
            )
        )
        assert run is not None
        assert run.evidence_json
        assert db.session.scalar(
            db.select(db.func.count(AgentExecutionLog.id)).where(
                AgentExecutionLog.workflow_id == payload["workflow_id"]
            )
        ) == 5
        assert db.session.scalar(
            db.select(db.func.count(ToolCallLog.id)).where(
                ToolCallLog.workflow_id == payload["workflow_id"]
            )
        ) >= 1


def test_weather_based_workflow_uses_mocked_weather(client, auth, monkeypatch):
    auth.login()
    monkeypatch.setattr(
        "bizpilot.agents.retriever.retrieve_weather",
        lambda: {
            "location": "Madurai",
            "temperature": 35,
            "condition": "Clear sky",
            "rain_probability": 5,
        },
    )
    response = client.post(
        "/api/agent/run",
        json={"query": "What offer should I provide based on Madurai weather?"},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["intent"] == "weather"
    assert "weather_tool" in payload["tools_used"]
    assert "cotton" in payload["decision"]["decision"].lower()


def test_follow_up_uses_short_term_memory(client, auth):
    auth.login()
    first = client.post(
        "/api/agent/run", json={"query": "Which product should I promote?"}
    ).get_json()
    second = client.post(
        "/api/agent/run",
        json={
            "query": "Why did you choose that?",
            "session_id": first["session_id"],
        },
    )
    payload = second.get_json()
    assert second.status_code == 200
    assert payload["intent"] == "follow_up"
    assert "because" in payload["decision"]["decision"].lower()
    assert payload["confidence"] > 0


def test_previous_decision_uses_deduplicated_long_term_memory(app, client, auth):
    auth.login()
    first = client.post(
        "/api/agent/run", json={"query": "Which products should I restock?"}
    ).get_json()
    client.post(
        "/api/agent/run",
        json={"query": "Which products should I restock?", "session_id": first["session_id"]},
    )
    previous = client.post(
        "/api/agent/run",
        json={
            "query": "What did you recommend previously for low-stock products?",
            "session_id": first["session_id"],
        },
    )
    payload = previous.get_json()
    assert previous.status_code == 200
    assert payload["intent"] == "previous_decision"
    assert "workflow" in payload["decision"]["reason"][0].lower()
    with app.app_context():
        memories = db.session.scalars(
            db.select(AgentMemory).where(
                AgentMemory.memory_key == "decision:inventory"
            )
        ).all()
        assert len(memories) == 1


def test_empty_and_unsupported_requests_are_safe(client, auth):
    auth.login()
    assert client.post("/api/agent/run", json={"query": ""}).status_code == 400
    response = client.post("/api/agent/run", json={"query": "Write a fantasy poem"})
    assert response.status_code == 200
    assert response.get_json()["intent"] == "unsupported"


def test_workflow_and_memory_apis_enforce_ownership(client, auth):
    auth.login()
    created = client.post(
        "/api/agent/run", json={"query": "Which products should I restock?"}
    ).get_json()
    assert client.get("/api/agent/workflows").status_code == 200
    assert client.get(
        f"/api/agent/workflows/{created['workflow_id']}"
    ).status_code == 200
    assert client.get("/api/memory/search?q=stock").status_code == 200
    auth.logout()
    auth.login("other@example.com", "password123")
    assert client.get(
        f"/api/agent/workflows/{created['workflow_id']}"
    ).status_code == 404
