"""Planning Agent: turn a classified request into a validated tool plan."""

from __future__ import annotations

import re

from .schemas import PlanningOutput
from ..graph.state import AgentWorkflowState, require_state_fields


class PlanningAgent:
    """Understand the objective and specify evidence required by later agents."""

    CATEGORY_BY_LEGACY_INTENT = {
        "inventory_management": "inventory",
        "sales_analysis": "sales",
        "expense_tracking": "expenses",
        "profit_analysis": "profit",
        "offer_recommendation": "marketing",
        "customer_feedback_analysis": "feedback",
        "weather_based_decision": "weather",
        "business_performance": "business_performance",
        "general_business_advice": "general_business",
    }

    TOOLS_BY_CATEGORY = {
        "inventory": [
            "low_stock_tool",
            "out_of_stock_tool",
            "best_selling_product_tool",
        ],
        "sales": [
            "sales_summary_tool",
            "best_selling_product_tool",
            "slow_moving_product_tool",
        ],
        "expenses": ["expense_summary_tool"],
        "profit": [
            "sales_summary_tool",
            "expense_summary_tool",
            "profit_calculator_tool",
            "product_performance_tool",
        ],
        "feedback": [
            "feedback_retrieval_tool",
            "feedback_category_tool",
            "product_lookup_tool",
        ],
        "marketing": [
            "product_lookup_tool",
            "best_selling_product_tool",
            "slow_moving_product_tool",
            "feedback_retrieval_tool",
        ],
        "weather": [
            "weather_tool",
            "product_lookup_tool",
            "best_selling_product_tool",
        ],
        "calculation": ["calculator_tool"],
        "business_performance": [
            "sales_summary_tool",
            "expense_summary_tool",
            "profit_calculator_tool",
            "product_performance_tool",
        ],
        "previous_decision": ["long_term_memory"],
        "follow_up": ["conversation_context"],
        "general_business": [
            "business_profile_tool",
            "sales_summary_tool",
            "expense_summary_tool",
            "low_stock_tool",
        ],
        "unsupported": [],
    }

    EXPECTED_OUTPUT_BY_CATEGORY = {
        "inventory": "ranked_restock_recommendations",
        "sales": "sales_performance_summary",
        "expenses": "expense_control_recommendations",
        "profit": "profit_estimate_and_actions",
        "feedback": "complaint_categories_and_actions",
        "marketing": "evidence_backed_promotion",
        "weather": "weather_based_offer",
        "calculation": "verified_calculation",
        "business_performance": "monthly_business_scorecard",
        "previous_decision": "previous_recommendation",
        "follow_up": "contextual_explanation",
        "general_business": "business_recommendation",
        "unsupported": "scope_guidance",
    }

    def run(self, state: AgentWorkflowState) -> dict:
        require_state_fields(state, "user_query", "coordination")
        query = state["user_query"]
        coordination = state["coordination"]
        category = self._category(query, coordination["intent"], state)
        required_tools = list(self.TOOLS_BY_CATEGORY[category])
        parameters = self._tool_parameters(query, coordination, required_tools)
        steps = [f"Use {name.replace('_', ' ')}" for name in required_tools]
        if not steps:
            steps = ["Explain which BizPilot business questions are supported"]
        steps.extend(
            [
                "Compare the retrieved evidence without inventing values",
                "Produce a confidence-scored business recommendation",
            ]
        )
        plan = PlanningOutput(
            intent=category,
            objective=self._objective(category, query),
            required_tools=required_tools,
            steps=steps,
            expected_output=self.EXPECTED_OUTPUT_BY_CATEGORY[category],
            tool_parameters=parameters,
        ).model_dump()
        return {
            "intent": category,
            "request_category": category,
            "plan": plan,
            "required_tools": required_tools,
            "agents_used": [*state.get("agents_used", []), "planning_agent"],
            "execution_trace": [
                *state.get("execution_trace", []),
                "Planning Agent",
            ],
        }

    def _category(
        self, query: str, legacy_intent: str, state: AgentWorkflowState
    ) -> str:
        lowered = query.lower().strip(" ?.!")
        context = state.get("short_term_context", [])
        if context and (
            lowered in {"why", "how", "explain", "why did you choose that"}
            or lowered.startswith(("why did", "why was", "explain that", "what about that"))
        ):
            return "follow_up"
        if any(
            phrase in lowered
            for phrase in (
                "previously",
                "previous decision",
                "last decision",
                "did you recommend",
                "recommended before",
            )
        ):
            return "previous_decision"
        if "calculat" in lowered and re.search(r"\d", lowered):
            return "calculation"
        category = self.CATEGORY_BY_LEGACY_INTENT.get(legacy_intent, "unsupported")
        business_terms = {
            "business",
            "product",
            "stock",
            "sale",
            "expense",
            "profit",
            "customer",
            "offer",
            "promote",
            "weather",
            "strategy",
            "recommend",
        }
        if category == "general_business" and not any(
            term in lowered for term in business_terms
        ):
            return "unsupported"
        return category

    @staticmethod
    def _objective(category: str, query: str) -> str:
        labels = {
            "inventory": "Identify and rank products that need restocking",
            "sales": "Summarize sales performance and product movement",
            "expenses": "Identify expenses that deserve review",
            "profit": "Estimate operating profit from recorded revenue and expenses",
            "feedback": "Identify customer complaint patterns and corrective actions",
            "marketing": "Choose a margin-aware product promotion",
            "weather": "Recommend an offer suited to configured local weather",
            "calculation": "Calculate the requested business metric",
            "business_performance": "Assess this month's overall business performance",
            "previous_decision": "Retrieve the most relevant previous recommendation",
            "follow_up": "Explain the preceding recommendation using its evidence",
            "general_business": "Provide grounded general business guidance",
            "unsupported": "Explain the supported business decision scope",
        }
        return labels.get(category, query[:240])

    def _tool_parameters(
        self, query: str, coordination: dict, required_tools: list[str]
    ) -> dict[str, dict]:
        period = coordination.get("time_period", "last_30_days")
        parameters = {
            tool: {"period": period}
            for tool in required_tools
            if tool
            in {
                "sales_summary_tool",
                "best_selling_product_tool",
                "slow_moving_product_tool",
                "product_performance_tool",
                "expense_summary_tool",
            }
        }
        if "feedback_retrieval_tool" in required_tools:
            parameters["feedback_retrieval_tool"] = {"recent": True}
        if "weather_tool" in required_tools:
            location_match = re.search(r"\b(?:in|for)\s+([A-Za-z ]+?)(?:\s+weather|\?|$)", query)
            if location_match:
                parameters["weather_tool"] = {"location": location_match.group(1).strip()}
        if "calculator_tool" in required_tools:
            values = self._extract_financial_values(query)
            parameters["calculator_tool"] = {"operation": "profit_margin", **values}
        return parameters

    @staticmethod
    def _extract_financial_values(query: str) -> dict[str, float]:
        values: dict[str, float] = {}
        patterns = {
            "revenue": r"(?:revenue|sales)\s*(?:of|is|=|:)?\s*[₹$]?\s*([\d,]+(?:\.\d+)?)",
            "expenses": r"(?:expenses?|costs?)\s*(?:of|is|=|:)?\s*[₹$]?\s*([\d,]+(?:\.\d+)?)",
        }
        for name, pattern in patterns.items():
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                values[name] = float(match.group(1).replace(",", ""))
        return values
