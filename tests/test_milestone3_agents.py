from __future__ import annotations

from bizpilot.agents.coordinator import CoordinatorAgent
from bizpilot.agents.planning_agent import PlanningAgent
from bizpilot.agents.research_agent import ResearchAgent
from bizpilot.services.confidence_service import calculate_confidence
from bizpilot.tools.registry import ToolRegistry


def _state(query: str, legacy_intent: str, **updates):
    state = {
        "workflow_id": "test-workflow",
        "user_query": query,
        "user_id": 1,
        "coordination": {
            "intent": legacy_intent,
            "time_period": "this_month",
            "original_prompt": query,
        },
        "short_term_context": [],
        "long_term_memories": [],
        "agents_used": [],
        "execution_trace": ["Coordinator"],
        "warnings": [],
        "tool_call_logs": [],
    }
    state.update(updates)
    return state


def test_planning_agent_creates_structured_inventory_plan():
    state = _state("Which products should I restock?", "inventory_management")
    result = PlanningAgent().run(state)
    assert result["intent"] == "inventory"
    assert result["plan"]["objective"]
    assert result["plan"]["expected_output"] == "ranked_restock_recommendations"
    assert result["required_tools"] == [
        "low_stock_tool",
        "out_of_stock_tool",
        "best_selling_product_tool",
    ]
    assert result["agents_used"] == ["planning_agent"]


def test_planning_agent_extracts_calculation_inputs():
    state = _state(
        "Calculate profit margin for revenue 50,000 and expenses 32,000",
        "profit_analysis",
    )
    result = PlanningAgent().run(state)
    assert result["intent"] == "calculation"
    params = result["plan"]["tool_parameters"]["calculator_tool"]
    assert params["revenue"] == 50000
    assert params["expenses"] == 32000


def test_tool_registry_returns_consistent_structured_result(app):
    with app.app_context():
        result, log = ToolRegistry().execute("low_stock_tool", 1, {})
    assert set(result) == {"success", "tool_name", "data", "message", "error"}
    assert result["success"] is True
    assert result["tool_name"] == "low_stock_tool"
    assert log["status"] == "success"
    assert log["execution_time_ms"] >= 0


def test_research_agent_records_one_tool_failure_without_crashing(app):
    class FailingRegistry:
        def execute(self, tool_name, user_id, parameters):
            if tool_name == "low_stock_tool":
                return (
                    {
                        "success": False,
                        "tool_name": tool_name,
                        "data": None,
                        "message": "Unavailable",
                        "error": "Unavailable",
                    },
                    {
                        "tool_name": tool_name,
                        "input_data": parameters,
                        "status": "failed",
                        "output_summary": "No output",
                        "error_message": "Unavailable",
                        "execution_time_ms": 1,
                    },
                )
            return (
                {
                    "success": True,
                    "tool_name": tool_name,
                    "data": [],
                    "message": "No rows",
                    "error": None,
                },
                {
                    "tool_name": tool_name,
                    "input_data": parameters,
                    "status": "success",
                    "output_summary": "Returned 0 item(s)",
                    "error_message": None,
                    "execution_time_ms": 1,
                },
            )

    state = _state(
        "Which products should I restock?",
        "inventory_management",
        plan={
            "tool_parameters": {},
            "required_tools": ["low_stock_tool", "out_of_stock_tool"],
        },
        required_tools=["low_stock_tool", "out_of_stock_tool"],
    )
    with app.app_context():
        result = ResearchAgent(FailingRegistry()).run(state)
    assert result["retrieval"]["retrieval_status"] == "partial"
    assert "low_stock_tool" in result["retrieval"]["missing_information"]
    assert result["evidence"]["out_of_stock_tool"] == []


def test_confidence_penalizes_missing_tools_and_rule_fallback():
    score = calculate_confidence(
        ["sales_summary_tool", "expense_summary_tool"],
        {"sales_summary_tool": {"success": True}},
        {"sales_summary_tool": {"total_revenue": 100}},
        "rule_based",
        ["Expense data unavailable"],
        0.9,
    )
    assert score == 0.67


def test_foundational_classifier_still_handles_invalid_scope():
    result = CoordinatorAgent().classify("Write me a fantasy poem")
    assert result["normalized_prompt"]
