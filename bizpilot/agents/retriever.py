"""Retriever Agent: collect and structure internal and external data."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func

from ..extensions import db
from ..models import (
    ChatMessage,
    CustomerFeedback,
    Expense,
    Product,
    Sale,
    SaleItem,
)
from ..services.weather_service import retrieve_weather


class RetrieverAgent:
    def execute(self, plan: dict, user_id: int) -> dict:
        retrieved: dict = {}
        missing: list[str] = []
        sources: list[str] = []

        for step in plan["steps"]:
            action = step["action"]
            params = step.get("params", {})
            if step.get("agent"):
                continue
            try:
                if action == "retrieve_inventory":
                    retrieved["inventory"] = self.retrieve_product_inventory(user_id)
                elif action == "retrieve_low_stock":
                    retrieved["low_stock"] = self.retrieve_low_stock_products(user_id)
                elif action == "retrieve_sales":
                    retrieved["sales"] = self.retrieve_sales_data(
                        user_id, params.get("period", "last_30_days")
                    )
                elif action == "retrieve_expenses":
                    retrieved["expenses"] = self.retrieve_expenses(
                        user_id, params.get("period", "last_30_days")
                    )
                elif action == "retrieve_feedback":
                    retrieved["feedback"] = self.retrieve_customer_feedback(
                        user_id, params.get("recent", True)
                    )
                elif action == "retrieve_best_sellers":
                    retrieved["best_sellers"] = self.retrieve_best_sellers(
                        user_id, params.get("period", "last_30_days")
                    )
                elif action == "retrieve_slow_movers":
                    retrieved["slow_movers"] = self.retrieve_slow_movers(
                        user_id, params.get("period", "last_30_days")
                    )
                elif action == "retrieve_weather":
                    retrieved["weather"] = retrieve_weather()
                sources.append(step["source"])
            except Exception:
                missing.append(action.replace("retrieve_", ""))

        return {
            "retrieved_data": retrieved,
            "missing_data": missing,
            "data_sources_used": list(dict.fromkeys(sources)),
        }

    @staticmethod
    def retrieve_product_inventory(user_id: int) -> list[dict]:
        products = db.session.scalars(
            db.select(Product)
            .where(Product.user_id == user_id, Product.is_active.is_(True))
            .order_by(Product.stock_quantity.asc(), Product.name.asc())
        ).all()
        return [product.to_dict() for product in products]

    @staticmethod
    def retrieve_low_stock_products(user_id: int) -> list[dict]:
        products = db.session.scalars(
            db.select(Product)
            .where(
                Product.user_id == user_id,
                Product.is_active.is_(True),
                Product.stock_quantity <= Product.reorder_level,
            )
            .order_by(Product.stock_quantity.asc())
        ).all()
        return [product.to_dict() for product in products]

    def retrieve_sales_data(self, user_id: int, period: str) -> dict:
        start, end = self.period_bounds(period)
        sales = db.session.scalars(
            db.select(Sale).where(
                Sale.user_id == user_id,
                Sale.is_active.is_(True),
                Sale.sale_date.between(start, end),
            )
        ).all()
        revenue = sum(float(sale.final_amount) for sale in sales)
        units = sum(item.quantity for sale in sales for item in sale.items)
        return {
            "period": period,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "total_revenue": round(revenue, 2),
            "total_orders": len(sales),
            "units_sold": units,
            "average_order_value": round(revenue / len(sales), 2) if sales else 0,
            "discounts_given": round(
                sum(float(sale.discount_amount) for sale in sales), 2
            ),
        }

    def retrieve_expenses(self, user_id: int, period: str) -> dict:
        start, end = self.period_bounds(period)
        expenses = db.session.scalars(
            db.select(Expense).where(
                Expense.user_id == user_id,
                Expense.expense_date.between(start, end),
            )
        ).all()
        categories: dict[str, float] = {}
        for expense in expenses:
            categories[expense.category] = categories.get(expense.category, 0) + float(
                expense.amount
            )
        return {
            "period": period,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "total_expenses": round(sum(categories.values()), 2),
            "record_count": len(expenses),
            "by_category": dict(
                sorted(categories.items(), key=lambda item: item[1], reverse=True)
            ),
        }

    @staticmethod
    def retrieve_customer_feedback(user_id: int, recent: bool = True) -> dict:
        statement = db.select(CustomerFeedback).where(
            CustomerFeedback.user_id == user_id
        )
        if recent:
            statement = statement.where(
                CustomerFeedback.feedback_date >= date.today() - timedelta(days=90)
            )
        feedback = db.session.scalars(
            statement.order_by(CustomerFeedback.feedback_date.desc())
        ).all()
        counts = {"positive": 0, "neutral": 0, "negative": 0}
        for item in feedback:
            counts[item.sentiment] = counts.get(item.sentiment, 0) + 1
        return {
            "average_rating": round(
                sum(item.rating for item in feedback) / len(feedback), 2
            )
            if feedback
            else 0,
            "total_feedback": len(feedback),
            "sentiment_distribution": counts,
            "unresolved_count": sum(not item.is_resolved for item in feedback),
            "recent_comments": [item.to_dict() for item in feedback[:8]],
        }

    def retrieve_best_sellers(self, user_id: int, period: str) -> list[dict]:
        start, end = self.period_bounds(period)
        rows = db.session.execute(
            db.select(
                Product.id,
                Product.name,
                Product.stock_quantity,
                Product.selling_price,
                Product.purchase_price,
                func.coalesce(func.sum(SaleItem.quantity), 0).label("units_sold"),
                func.coalesce(func.sum(SaleItem.total_price), 0).label("revenue"),
            )
            .join(SaleItem, SaleItem.product_id == Product.id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(
                Product.user_id == user_id,
                Product.is_active.is_(True),
                Sale.is_active.is_(True),
                Sale.sale_date.between(start, end),
            )
            .group_by(Product.id)
            .order_by(db.desc("units_sold"))
            .limit(5)
        ).all()
        return [
            {
                "product_id": row.id,
                "name": row.name,
                "units_sold": int(row.units_sold),
                "revenue": float(row.revenue),
                "stock_quantity": row.stock_quantity,
                "selling_price": float(row.selling_price),
                "purchase_price": float(row.purchase_price),
            }
            for row in rows
        ]

    def retrieve_slow_movers(self, user_id: int, period: str) -> list[dict]:
        start, end = self.period_bounds(period)
        subquery = (
            db.select(
                SaleItem.product_id,
                func.sum(SaleItem.quantity).label("units_sold"),
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.sale_date.between(start, end), Sale.is_active.is_(True))
            .group_by(SaleItem.product_id)
            .subquery()
        )
        rows = db.session.execute(
            db.select(
                Product.id,
                Product.name,
                Product.stock_quantity,
                Product.selling_price,
                Product.purchase_price,
                func.coalesce(subquery.c.units_sold, 0).label("units_sold"),
            )
            .outerjoin(subquery, subquery.c.product_id == Product.id)
            .where(
                Product.user_id == user_id,
                Product.is_active.is_(True),
                Product.stock_quantity > 0,
            )
            .order_by(db.asc("units_sold"), Product.stock_quantity.desc())
            .limit(5)
        ).all()
        return [
            {
                "product_id": row.id,
                "name": row.name,
                "units_sold": int(row.units_sold),
                "stock_quantity": row.stock_quantity,
                "selling_price": float(row.selling_price),
                "purchase_price": float(row.purchase_price),
            }
            for row in rows
        ]

    @staticmethod
    def retrieve_chat_history(user_id: int, session_id: int) -> list[dict]:
        messages = db.session.scalars(
            db.select(ChatMessage)
            .where(
                ChatMessage.user_id == user_id,
                ChatMessage.session_id == session_id,
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(10)
        ).all()
        return [
            {"role": message.role, "message_text": message.message_text}
            for message in reversed(messages)
        ]

    @staticmethod
    def calculate_profit_margin(cost: float, price: float) -> float:
        if price <= 0:
            return 0.0
        return round((price - cost) / price * 100, 2)

    @staticmethod
    def period_bounds(period: str) -> tuple[date, date]:
        today = date.today()
        if period == "today":
            return today, today
        if period == "yesterday":
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        if period == "this_week":
            return today - timedelta(days=today.weekday()), today
        if period == "last_week":
            start_this_week = today - timedelta(days=today.weekday())
            return start_this_week - timedelta(days=7), start_this_week - timedelta(days=1)
        if period == "this_month":
            return today.replace(day=1), today
        if period == "last_month":
            last_day = today.replace(day=1) - timedelta(days=1)
            return last_day.replace(day=1), last_day
        return today - timedelta(days=29), today

