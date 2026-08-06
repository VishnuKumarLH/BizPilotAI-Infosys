from __future__ import annotations

from bizpilot.extensions import db
from bizpilot.models import AgentExecutionLog, ChatMessage, ChatSession


def test_chat_runs_five_agent_pipeline_and_persists_trace(app, client, auth):
    auth.login()
    response = client.post(
        "/chat/send", json={"prompt": "What offer should I make this week?"}
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["workflow"]["coordinator"]["intent"] == "offer_recommendation"
    assert payload["response"]["ai_provider"] == "rule_based"
    assert payload["response"]["fallback_used"] is True
    assert payload["response"]["recommendations"]
    assert set(payload["workflow"]) == {
        "coordinator",
        "orchestrator",
        "retriever",
        "decision",
        "response",
    }
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(ChatMessage.id))) == 2
        logs = db.session.scalars(
            db.select(AgentExecutionLog).order_by(AgentExecutionLog.execution_order)
        ).all()
        assert [log.agent_name for log in logs] == [
            "coordinator",
            "planning_agent",
            "research_agent",
            "analysis_decision_agent",
            "response_agent",
        ]


def test_chat_session_load_rename_archive_and_history(client, auth):
    auth.login()
    first = client.post("/chat/send", json={"prompt": "How are my sales today?"})
    session_id = first.get_json()["session"]["id"]
    second = client.post(
        "/chat/send",
        json={"prompt": "What is the average order value?", "session_id": session_id},
    )
    assert second.status_code == 200
    detail = client.get(f"/chat/sessions/{session_id}").get_json()
    assert len(detail["messages"]) == 4
    history = client.get(f"/chat/history?session_id={session_id}").get_json()
    assert len(history["messages"]) == 4
    renamed = client.post(
        f"/chat/sessions/{session_id}/rename", json={"title": "Daily sales review"}
    )
    assert renamed.status_code == 200
    assert renamed.get_json()["session"]["session_title"] == "Daily sales review"
    assert client.delete(f"/chat/sessions/{session_id}").status_code == 200
    assert client.get(f"/chat/sessions/{session_id}").status_code == 404


def test_weather_prompt_uses_external_retriever(app, client, auth, monkeypatch):
    auth.login()
    monkeypatch.setattr(
        "bizpilot.agents.retriever.retrieve_weather",
        lambda: {
            "location": "Madurai",
            "temperature": 34,
            "condition": "Clear sky",
            "rain_probability": 5,
        },
    )
    response = client.post(
        "/chat/send",
        json={"prompt": "What offer suits today's weather in Madurai?"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["workflow"]["coordinator"]["requires_weather_data"] is True
    assert payload["workflow"]["retriever"]["retrieved_data"]["weather"]["temperature"] == 34
    assert "cotton" in payload["response"]["final_decision"].lower()


def test_cross_user_session_access_is_blocked(app, client, auth):
    auth.login()
    response = client.post("/chat/send", json={"prompt": "Show my sales"})
    session_id = response.get_json()["session"]["id"]
    auth.logout()
    auth.login("other@example.com", "password123")
    assert client.get(f"/chat/sessions/{session_id}").status_code == 404
    assert client.delete(f"/chat/sessions/{session_id}").status_code == 404
