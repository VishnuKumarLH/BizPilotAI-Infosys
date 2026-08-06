from __future__ import annotations

import pytest
import requests

from bizpilot.agents.coordinator import CoordinatorAgent
from bizpilot.agents.orchestrator import OrchestratorAgent
from bizpilot.agents.decision import DecisionAgent
from bizpilot.services.ai_service import AIService, ProviderFailure


@pytest.mark.parametrize(
    ("prompt", "intent"),
    [
        ("Which products are running low on stock?", "inventory_management"),
        ("How are my sales this month?", "sales_analysis"),
        ("What offer should I make this week?", "offer_recommendation"),
        ("What are my total expenses this month?", "expense_tracking"),
        ("Am I making a profit?", "profit_analysis"),
        ("Summarize recent customer complaints", "customer_feedback_analysis"),
        ("What's the weather in Madurai today?", "weather_based_decision"),
        ("How is my business performing overall?", "business_performance"),
        ("Give me general strategy advice", "general_business_advice"),
    ],
)
def test_coordinator_classifies_examples(prompt, intent):
    result = CoordinatorAgent().classify(prompt)
    assert result["intent"] == intent
    assert result["confidence"] >= 0.62
    assert result["normalized_prompt"]


def test_weather_adds_external_tool_requirement():
    result = CoordinatorAgent().classify(
        "What offer should I run based on today's rainy weather?"
    )
    assert result["intent"] == "weather_based_decision"
    assert result["requires_weather_data"] is True
    assert "weather" in result["business_areas"]


def test_orchestrator_only_plans_and_orders_agents():
    coordination = CoordinatorAgent().classify("What offer should I make this week?")
    plan = OrchestratorAgent().create_plan(coordination)
    actions = [step["action"] for step in plan["steps"]]
    assert actions[:3] == [
        "retrieve_sales",
        "retrieve_inventory",
        "retrieve_best_sellers",
    ]
    assert actions[-1] == "format_response"
    assert plan["fallback_strategy"] == "rule_based_if_ai_fails"


def test_ai_service_falls_back_to_groq_after_retryable_gemini_failure(app, monkeypatch):
    app.config.update(
        GEMINI_API_KEY="configured",
        GROQ_API_KEY="configured",
        AI_MAX_RETRIES=1,
    )
    calls = []

    def fake_call(self, provider, api_key, prompt):
        calls.append(provider)
        if provider == "gemini":
            raise ProviderFailure("rate limited", retryable=True)
        return (
            '{"key_findings":[],"final_decision":"Use Groq",'
            '"reason":[],"recommendations":[],"avoid_actions":[],'
            '"priority":"medium","confidence":0.8}'
        )

    monkeypatch.setattr(AIService, "_call_provider", fake_call)
    with app.app_context():
        decision, provider, errors = AIService().analyze("prompt")
    assert provider == "groq"
    assert decision["final_decision"] == "Use Groq"
    assert calls == ["gemini", "gemini", "groq"]
    assert len(errors) == 2


def test_invalid_gemini_credentials_switch_to_configured_fallback(app, monkeypatch):
    app.config.update(GEMINI_API_KEY="bad", GROQ_API_KEY="configured")
    calls = []

    def fake_call(self, provider, api_key, prompt):
        calls.append(provider)
        raise ProviderFailure("invalid credentials", False, True)

    monkeypatch.setattr(AIService, "_call_provider", fake_call)
    with app.app_context():
        decision, provider, errors = AIService().analyze("prompt")
    assert decision is None
    assert provider is None
    assert calls == ["gemini", "groq"]
    assert errors


def test_network_timeout_is_marked_retryable(app, monkeypatch):
    monkeypatch.setattr(
        "bizpilot.services.ai_service.requests.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.Timeout()),
    )
    with app.app_context(), pytest.raises(ProviderFailure) as caught:
        AIService()._call_provider("gemini", "configured", "prompt")
    assert caught.value.retryable is True


def test_offer_rule_never_forces_unprofitable_discount():
    decision = DecisionAgent()._offer_decision(
        [
            {
                "name": "Low Margin Leader",
                "selling_price": 100,
                "purchase_price": 99,
                "units_sold": 10,
                "stock_quantity": 20,
            }
        ],
        [
            {
                "name": "Low Margin Slow Mover",
                "selling_price": 100,
                "purchase_price": 99,
                "units_sold": 0,
                "stock_quantity": 20,
            }
        ],
        {"average_rating": 4},
    )
    assert "full price" in decision["final_decision"]
