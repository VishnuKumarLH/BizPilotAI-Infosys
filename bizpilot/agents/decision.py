"""Decision Agent: the only agent permitted to call an AI model."""

from __future__ import annotations

from ..services.ai_service import AIService
from .prompts import build_decision_prompt


class DecisionAgent:
    def __init__(self) -> None:
        self.ai = AIService()

    def decide(
        self, coordination: dict, retrieval: dict, history: list[dict] | None = None
    ) -> dict:
        prompt = self._build_prompt(coordination, retrieval, history or [])
        ai_decision, provider, errors = self.ai.analyze(prompt)
        if ai_decision is not None:
            return {
                **ai_decision,
                "ai_provider": provider,
                "fallback_used": provider != "gemini",
                "provider_errors": errors,
            }

        decision = self._rule_based(coordination["intent"], retrieval["retrieved_data"])
        return {
            **decision,
            "ai_provider": "rule_based",
            "fallback_used": True,
            "provider_errors": errors,
        }

    @staticmethod
    def _build_prompt(coordination: dict, retrieval: dict, history: list[dict]) -> str:
        return build_decision_prompt(
            coordination, retrieval, history, "the connected business"
        )

    def _rule_based(self, intent: str, data: dict) -> dict:
        inventory = data.get("inventory", [])
        low_stock = data.get("low_stock") or [
            item
            for item in inventory
            if item.get("stock_status") in {"low_stock", "out_of_stock"}
        ]
        sales = data.get("sales", {})
        expenses = data.get("expenses", {})
        best = data.get("best_sellers", [])
        slow = data.get("slow_movers", [])
        feedback = data.get("feedback", {})
        weather = data.get("weather", {})

        if intent == "inventory_management":
            return self._inventory_decision(low_stock, best)
        if intent == "sales_analysis":
            return self._sales_decision(sales, best, slow)
        if intent == "expense_tracking":
            return self._expense_decision(expenses)
        if intent == "profit_analysis":
            return self._profit_decision(sales, expenses)
        if intent == "offer_recommendation":
            return self._offer_decision(best, slow, feedback)
        if intent == "customer_feedback_analysis":
            return self._feedback_decision(feedback)
        if intent == "weather_based_decision":
            return self._weather_decision(weather, inventory)
        return self._overall_decision(sales, expenses, low_stock, feedback)

    @staticmethod
    def _base(
        findings: list[str],
        decision: str,
        reasons: list[str],
        recommendations: list[str],
        avoid: list[str],
        priority: str = "medium",
        confidence: float = 0.70,
    ) -> dict:
        return {
            "key_findings": findings,
            "final_decision": decision,
            "reason": reasons,
            "recommendations": recommendations,
            "avoid_actions": avoid,
            "priority": priority,
            "confidence": confidence,
        }

    def _inventory_decision(self, low_stock: list[dict], best: list[dict]) -> dict:
        if not low_stock:
            return self._base(
                ["No active product is at or below its reorder level."],
                "Stock is healthy; review demand before placing a new order.",
                ["Current inventory has no immediate shortage."],
                ["Monitor fast-selling items weekly.", "Use available stock for promotions."],
                ["Avoid broad restocking without demand evidence."],
                confidence=0.86,
            )
        urgent = sorted(
            low_stock, key=lambda item: (item["stock_quantity"] != 0, item["stock_quantity"])
        )
        names = ", ".join(item["name"] for item in urgent[:4])
        best_names = {item["name"] for item in best}
        priority_items = [item for item in urgent if item["name"] in best_names] or urgent
        return self._base(
            [
                f"{len(low_stock)} product(s) are at or below reorder level.",
                f"Most urgent: {names}.",
            ],
            f"Restock {priority_items[0]['name']} first and review the remaining shortages.",
            ["The recommendation prioritizes shortage severity and recent demand."],
            [
                f"Raise {item['name']} toward {min(item['max_stock_level'], max(item['reorder_level'] * 2, item['reorder_level'] + 5))} units."
                for item in priority_items[:3]
            ],
            ["Do not restock slow-moving products beyond their reorder level."],
            "high",
            0.82,
        )

    def _sales_decision(self, sales: dict, best: list[dict], slow: list[dict]) -> dict:
        revenue = sales.get("total_revenue", 0)
        orders = sales.get("total_orders", 0)
        top = best[0] if best else None
        findings = [
            f"Revenue is ₹{revenue:,.2f} from {orders} order(s) in the selected period.",
            f"Average order value is ₹{sales.get('average_order_value', 0):,.2f}.",
        ]
        if top:
            findings.append(f"{top['name']} leads with {top['units_sold']} unit(s) sold.")
        return self._base(
            findings,
            "Protect the strongest seller and use it to lift low-velocity inventory.",
            ["The sales mix shows where demand already exists."],
            [
                "Keep the top seller visible and in stock.",
                "Track revenue and units sold weekly.",
                "Test a margin-safe bundle with one slow mover.",
            ],
            ["Avoid discounting the best seller on its own."],
            "medium" if orders else "high",
            0.78,
        )

    def _expense_decision(self, expenses: dict) -> dict:
        categories = expenses.get("by_category", {})
        highest = next(iter(categories.items()), ("No category", 0))
        return self._base(
            [
                f"Total expenses are ₹{expenses.get('total_expenses', 0):,.2f}.",
                f"The largest category is {highest[0]} at ₹{highest[1]:,.2f}.",
            ],
            f"Review {highest[0]} first for savings without disrupting sales.",
            ["The largest category offers the biggest potential impact."],
            [
                f"Audit each {highest[0]} charge.",
                "Separate recurring and discretionary costs.",
                "Set a monthly category budget.",
            ],
            ["Do not cut customer-facing essentials without measuring the effect."],
            "medium",
            0.84,
        )

    def _profit_decision(self, sales: dict, expenses: dict) -> dict:
        revenue = sales.get("total_revenue", 0)
        total_expenses = expenses.get("total_expenses", 0)
        operating_surplus = revenue - total_expenses
        label = "surplus" if operating_surplus >= 0 else "shortfall"
        return self._base(
            [
                f"Revenue is ₹{revenue:,.2f}.",
                f"Recorded expenses are ₹{total_expenses:,.2f}.",
                f"Revenue less recorded expenses is a ₹{abs(operating_surplus):,.2f} {label}.",
            ],
            (
                "Maintain profitable sales while tightening the largest expense category."
                if operating_surplus >= 0
                else "Prioritize cash recovery: increase margin-safe sales and reduce discretionary costs."
            ),
            ["This is an operating estimate based on the records available."],
            [
                "Confirm product cost of goods before treating this as net profit.",
                "Review weekly revenue and expense movement.",
            ],
            ["Do not treat revenue as profit or ignore unrecorded costs."],
            "high" if operating_surplus < 0 else "medium",
            0.76,
        )

    def _offer_decision(
        self, best: list[dict], slow: list[dict], feedback: dict
    ) -> dict:
        if best and slow:
            leader, laggard = best[0], slow[0]
            combined = float(leader["selling_price"]) + float(laggard["selling_price"])
            cost = float(leader["purchase_price"]) + float(laggard["purchase_price"])
            max_safe = max(0, int(((combined - cost) / combined * 100) - 5))
            discount = min(15, max_safe)
            offer = (
                f"at {discount}% off"
                if discount >= 5
                else "at full price with a low-cost service perk"
            )
            return self._base(
                [
                    f"{leader['name']} is a leading seller.",
                    f"{laggard['name']} has {laggard['stock_quantity']} in stock and only {laggard['units_sold']} recent sale(s).",
                    f"Recent customer rating averages {feedback.get('average_rating', 0):.1f}/5.",
                ],
                f"Bundle {leader['name']} with {laggard['name']} {offer} for 7 days.",
                ["The strong product can create demand for a slow mover while retaining margin."],
                [
                    "Run the bundle for one week.",
                    "Feature the combined saving at the counter and on social media.",
                    "Track daily unit sales and stop if margin falls below target.",
                ],
                [
                    f"Do not discount {leader['name']} individually.",
                    f"Do not reorder {laggard['name']} until existing stock moves.",
                ],
                "high",
                0.80,
            )
        return self._base(
            ["There is not enough matched sales and stock data to form a safe bundle."],
            "Collect more sales history before launching a broad promotion.",
            ["A margin-safe offer needs a proven seller and an identified slow mover."],
            ["Use a small, time-boxed promotion.", "Track product-level sales."],
            ["Avoid store-wide discounting."],
            "medium",
            0.68,
        )

    def _feedback_decision(self, feedback: dict) -> dict:
        negative = feedback.get("sentiment_distribution", {}).get("negative", 0)
        unresolved = feedback.get("unresolved_count", 0)
        comments = feedback.get("recent_comments", [])
        issue = next((item for item in comments if item["sentiment"] == "negative"), None)
        recommendations = [
            "Contact unresolved customers within 24 hours.",
            "Group repeated comments by product and issue.",
            "Confirm improvements with a follow-up.",
        ]
        if issue:
            recommendations.insert(
                0, f"Review the issue reported for {issue.get('product_name') or 'the product'}."
            )
        return self._base(
            [
                f"Average rating is {feedback.get('average_rating', 0):.1f}/5.",
                f"{negative} negative and {unresolved} unresolved feedback item(s) were found.",
            ],
            "Resolve the oldest negative feedback first, then address repeated product issues.",
            ["Unresolved negative experiences pose the highest retention risk."],
            recommendations,
            ["Do not mark feedback resolved without documenting the outcome."],
            "high" if unresolved else "medium",
            0.83,
        )

    def _weather_decision(self, weather: dict, inventory: list[dict]) -> dict:
        temp = weather.get("temperature")
        rain = weather.get("rain_probability") or 0
        condition = weather.get("condition", "Unknown")
        hot = temp is not None and float(temp) >= 30
        rainy = rain >= 50 or "rain" in condition.lower()
        if rainy:
            terms = ("polyester", "dark", "quick")
            theme = "rain-ready practical wear"
        elif hot:
            terms = ("cotton", "linen", "white", "beige")
            theme = "light cotton and linen styles"
        else:
            terms = ("shirt", "trouser", "denim")
            theme = "versatile layered outfits"
        suitable = [
            item for item in inventory if any(term in str(item).lower() for term in terms)
        ]
        names = ", ".join(item["name"] for item in suitable[:3]) or "available seasonal items"
        return self._base(
            [
                f"{weather.get('location', 'Local')} weather is {condition} at {temp}°C.",
                f"Rain probability is {rain}%.",
                f"Suitable available products include {names}.",
            ],
            f"Feature {theme} today using in-stock products only.",
            ["The product theme matches current local conditions."],
            [
                f"Place {names} in the primary display.",
                "Use a same-day weather message in store and online.",
                "Recheck the forecast before extending the campaign.",
            ],
            ["Avoid promoting out-of-stock seasonal products."],
            "medium",
            0.79,
        )

    def _overall_decision(
        self, sales: dict, expenses: dict, low_stock: list[dict], feedback: dict
    ) -> dict:
        revenue = sales.get("total_revenue", 0)
        total_expenses = expenses.get("total_expenses", 0)
        unresolved = feedback.get("unresolved_count", 0)
        return self._base(
            [
                f"Revenue is ₹{revenue:,.2f} against ₹{total_expenses:,.2f} in recorded expenses.",
                f"{len(low_stock)} product(s) need stock attention.",
                f"{unresolved} customer feedback item(s) remain unresolved.",
            ],
            "Protect cash flow first, then resolve critical stock and customer issues in that order.",
            ["The priority balances financial health, sales continuity, and retention."],
            [
                "Review the revenue-versus-expense gap.",
                "Restock proven sellers that are low or out of stock.",
                "Close unresolved negative feedback.",
            ],
            ["Avoid adding inventory that has weak recent demand."],
            "high",
            0.77,
        )
