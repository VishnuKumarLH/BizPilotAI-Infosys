"""Central tool registry with consistent results and sanitized call telemetry."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Callable

from flask import current_app

from ..agents import retriever as retriever_module
from ..agents.retriever import RetrieverAgent
from ..extensions import db
from ..models import Product, User


logger = logging.getLogger(__name__)


class ToolInputError(ValueError):
    """Raised when a tool receives missing or invalid public input."""


class ToolRegistry:
    """Invoke named tools without exposing ORM objects to workflow state."""

    def __init__(self) -> None:
        self.retriever = RetrieverAgent()
        self._tools: dict[str, Callable[[int, dict], Any]] = {
            "product_lookup_tool": self._product_lookup,
            "low_stock_tool": self._low_stock,
            "out_of_stock_tool": self._out_of_stock,
            "sales_summary_tool": self._sales_summary,
            "best_selling_product_tool": self._best_sellers,
            "slow_moving_product_tool": self._slow_movers,
            "product_performance_tool": self._product_performance,
            "expense_summary_tool": self._expense_summary,
            "profit_calculator_tool": self._profit_calculator,
            "feedback_retrieval_tool": self._feedback_retrieval,
            "feedback_category_tool": self._feedback_categories,
            "business_profile_tool": self._business_profile,
            "weather_tool": self._weather,
            "calculator_tool": self._calculator,
        }

    @property
    def names(self) -> list[str]:
        return sorted(self._tools)

    def execute(
        self, tool_name: str, user_id: int, parameters: dict | None = None
    ) -> tuple[dict, dict]:
        """Return a standardized tool result and a database-ready telemetry entry."""

        params = self._sanitize_input(parameters or {})
        started = perf_counter()
        status = "success"
        error_message = None
        try:
            operation = self._tools.get(tool_name)
            if operation is None:
                raise ToolInputError(f"Unsupported tool: {tool_name}")
            data = operation(user_id, params)
            result = {
                "success": True,
                "tool_name": tool_name,
                "data": data,
                "message": self._success_message(data),
                "error": None,
            }
        except ToolInputError as exc:
            status = "failed"
            error_message = str(exc)
            result = self._failure(tool_name, str(exc))
        except Exception as exc:  # one tool failure must not end the workflow
            logger.exception("Tool %s failed", tool_name)
            status = "failed"
            error_message = type(exc).__name__
            result = self._failure(
                tool_name, "The requested data source is temporarily unavailable."
            )
        elapsed = round((perf_counter() - started) * 1000)
        log = {
            "tool_name": tool_name,
            "input_data": params,
            "status": status,
            "output_summary": self._summarize(result.get("data")),
            "error_message": error_message,
            "execution_time_ms": elapsed,
        }
        logger.info("Tool %s completed with status=%s in %sms", tool_name, status, elapsed)
        return result, log

    @staticmethod
    def _failure(tool_name: str, message: str) -> dict:
        return {
            "success": False,
            "tool_name": tool_name,
            "data": None,
            "message": message,
            "error": message,
        }

    @staticmethod
    def _sanitize_input(parameters: dict) -> dict:
        blocked = {"api_key", "secret", "password", "token", "database_url"}
        return {
            str(key): value
            for key, value in parameters.items()
            if str(key).lower() not in blocked
            and isinstance(value, (str, int, float, bool, type(None), list, dict))
        }

    @staticmethod
    def _success_message(data: Any) -> str:
        if data in (None, [], {}):
            return "The tool completed successfully, but no matching records were found."
        return "Tool completed successfully."

    @staticmethod
    def _summarize(data: Any) -> str:
        if data is None:
            return "No output"
        if isinstance(data, list):
            return f"Returned {len(data)} item(s)"
        if isinstance(data, dict):
            return "Returned fields: " + ", ".join(list(data)[:8])
        return str(data)[:240]

    def _product_lookup(self, user_id: int, params: dict) -> list[dict]:
        statement = db.select(Product).where(
            Product.user_id == user_id, Product.is_active.is_(True)
        )
        search = str(params.get("search", "")).strip()
        if search:
            statement = statement.where(Product.name.ilike(f"%{search}%"))
        products = db.session.scalars(statement.order_by(Product.name).limit(100)).all()
        return [product.to_dict() for product in products]

    def _low_stock(self, user_id: int, params: dict) -> list[dict]:
        return self.retriever.retrieve_low_stock_products(user_id)

    def _out_of_stock(self, user_id: int, params: dict) -> list[dict]:
        products = db.session.scalars(
            db.select(Product)
            .where(
                Product.user_id == user_id,
                Product.is_active.is_(True),
                Product.stock_quantity == 0,
            )
            .order_by(Product.name)
        ).all()
        return [product.to_dict() for product in products]

    def _sales_summary(self, user_id: int, params: dict) -> dict:
        return self.retriever.retrieve_sales_data(
            user_id, str(params.get("period", "last_30_days"))
        )

    def _best_sellers(self, user_id: int, params: dict) -> list[dict]:
        return self.retriever.retrieve_best_sellers(
            user_id, str(params.get("period", "last_30_days"))
        )

    def _slow_movers(self, user_id: int, params: dict) -> list[dict]:
        return self.retriever.retrieve_slow_movers(
            user_id, str(params.get("period", "last_30_days"))
        )

    def _product_performance(self, user_id: int, params: dict) -> dict:
        period = str(params.get("period", "last_30_days"))
        return {
            "best_sellers": self.retriever.retrieve_best_sellers(user_id, period),
            "slow_movers": self.retriever.retrieve_slow_movers(user_id, period),
        }

    def _expense_summary(self, user_id: int, params: dict) -> dict:
        return self.retriever.retrieve_expenses(
            user_id, str(params.get("period", "last_30_days"))
        )

    def _profit_calculator(self, user_id: int, params: dict) -> dict:
        revenue = self._number(params, "revenue")
        expenses = self._number(params, "expenses")
        profit = revenue - expenses
        margin = (profit / revenue * 100) if revenue else 0
        return {
            "revenue": round(revenue, 2),
            "expenses": round(expenses, 2),
            "estimated_profit": round(profit, 2),
            "profit_margin_percent": round(margin, 2),
        }

    def _feedback_retrieval(self, user_id: int, params: dict) -> dict:
        return self.retriever.retrieve_customer_feedback(
            user_id, bool(params.get("recent", True))
        )

    def _feedback_categories(self, user_id: int, params: dict) -> dict:
        feedback = self.retriever.retrieve_customer_feedback(user_id, True)
        categories = {
            "fit_or_size": ("fit", "size", "tight", "loose"),
            "quality": ("quality", "stitch", "tear", "damage", "fabric"),
            "price": ("price", "cost", "expensive", "value"),
            "service": ("service", "staff", "wait", "exchange"),
            "availability": ("stock", "available", "colour", "color"),
        }
        counts = {name: 0 for name in categories}
        products: dict[str, int] = {}
        severe = 0
        for item in feedback.get("recent_comments", []):
            if item.get("sentiment") != "negative" and int(item.get("rating", 5)) > 2:
                continue
            text = str(item.get("feedback_text", "")).lower()
            severe += int(int(item.get("rating", 5)) <= 2)
            for name, words in categories.items():
                if any(word in text for word in words):
                    counts[name] += 1
            product = item.get("product_name")
            if product:
                products[product] = products.get(product, 0) + 1
        ranked = [
            {"category": name, "count": count}
            for name, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
            if count
        ]
        return {
            "complaint_categories": ranked,
            "frequently_mentioned_products": [
                {"product": name, "count": count}
                for name, count in sorted(products.items(), key=lambda pair: pair[1], reverse=True)
            ],
            "severe_complaints": severe,
        }

    @staticmethod
    def _business_profile(user_id: int, params: dict) -> dict:
        user = db.session.get(User, user_id)
        if user is None:
            raise ToolInputError("Business profile was not found.")
        return {
            "business_name": user.business_name,
            "business_type": user.business_type,
            "business_address": user.business_address,
            "business_phone": user.business_phone,
        }

    @staticmethod
    def _weather(user_id: int, params: dict) -> dict:
        configured = str(current_app.config["WEATHER_LOCATION"])
        location = str(params.get("location") or configured).strip()
        if location.casefold() != configured.casefold():
            raise ToolInputError(
                f"Weather is currently configured only for {configured}."
            )
        # Use the existing retriever module entry point so legacy integrations and
        # tests can replace the external weather call without live internet.
        return retriever_module.retrieve_weather()

    def _calculator(self, user_id: int, params: dict) -> dict:
        operation = str(params.get("operation", "profit_margin"))
        if operation == "profit_margin":
            return self._profit_calculator(user_id, params)
        if operation == "percentage":
            value = self._number(params, "value")
            total = self._number(params, "total")
            return {"percentage": round(value / total * 100, 2) if total else 0}
        raise ToolInputError(f"Unsupported calculation: {operation}")

    @staticmethod
    def _number(params: dict, name: str) -> float:
        if name not in params:
            raise ToolInputError(f"Missing calculation input: {name}")
        try:
            value = float(params[name])
        except (TypeError, ValueError) as exc:
            raise ToolInputError(f"Invalid calculation input: {name}") from exc
        if value < 0:
            raise ToolInputError(f"Calculation input cannot be negative: {name}")
        return value
