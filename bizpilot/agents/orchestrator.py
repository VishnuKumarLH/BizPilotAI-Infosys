"""Pure-Python Orchestrator Agent: create deterministic execution plans."""

from __future__ import annotations


class OrchestratorAgent:
    ACTIONS_BY_INTENT = {
        "inventory_management": [
            ("retrieve_inventory", "products_table"),
            ("retrieve_low_stock", "products_table"),
            ("retrieve_best_sellers", "sales_and_sale_items_tables"),
        ],
        "sales_analysis": [
            ("retrieve_sales", "sales_table"),
            ("retrieve_best_sellers", "sale_items_table"),
            ("retrieve_slow_movers", "products_and_sale_items_tables"),
        ],
        "expense_tracking": [
            ("retrieve_expenses", "expenses_table"),
        ],
        "profit_analysis": [
            ("retrieve_sales", "sales_table"),
            ("retrieve_expenses", "expenses_table"),
            ("retrieve_best_sellers", "sale_items_table"),
        ],
        "offer_recommendation": [
            ("retrieve_sales", "sales_table"),
            ("retrieve_inventory", "products_table"),
            ("retrieve_best_sellers", "sale_items_table"),
            ("retrieve_slow_movers", "products_and_sale_items_tables"),
            ("retrieve_feedback", "customer_feedback_table"),
        ],
        "customer_feedback_analysis": [
            ("retrieve_feedback", "customer_feedback_table"),
        ],
        "weather_based_decision": [
            ("retrieve_weather", "open_meteo_api"),
            ("retrieve_inventory", "products_table"),
            ("retrieve_best_sellers", "sale_items_table"),
        ],
        "business_performance": [
            ("retrieve_sales", "sales_table"),
            ("retrieve_inventory", "products_table"),
            ("retrieve_expenses", "expenses_table"),
            ("retrieve_feedback", "customer_feedback_table"),
            ("retrieve_best_sellers", "sale_items_table"),
        ],
        "general_business_advice": [
            ("retrieve_sales", "sales_table"),
            ("retrieve_inventory", "products_table"),
            ("retrieve_expenses", "expenses_table"),
        ],
    }

    def create_plan(self, coordination: dict) -> dict:
        actions = list(self.ACTIONS_BY_INTENT[coordination["intent"]])
        if coordination["requires_weather_data"] and not any(
            action == "retrieve_weather" for action, _ in actions
        ):
            actions.insert(0, ("retrieve_weather", "open_meteo_api"))

        steps = []
        for index, (action, source) in enumerate(actions, start=1):
            params = {}
            if action in {
                "retrieve_sales",
                "retrieve_best_sellers",
                "retrieve_slow_movers",
                "retrieve_expenses",
            }:
                params["period"] = coordination["time_period"]
            if action == "retrieve_feedback":
                params["recent"] = True
            steps.append(
                {"step": index, "action": action, "source": source, "params": params}
            )

        decision_step = len(steps) + 1
        steps.append(
            {
                "step": decision_step,
                "action": f"analyze_{coordination['intent']}",
                "agent": "decision",
                "data": [f"step{i}" for i in range(1, decision_step)],
            }
        )
        steps.append(
            {
                "step": decision_step + 1,
                "action": "format_response",
                "agent": "response",
                "data": [f"step{decision_step}"],
            }
        )
        return {
            "steps": steps,
            "estimated_time_ms": 1200 + (len(actions) * 250),
            "fallback_strategy": "rule_based_if_ai_fails",
        }

