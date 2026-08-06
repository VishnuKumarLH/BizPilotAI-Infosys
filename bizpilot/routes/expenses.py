"""Expense CRUD and category summaries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Expense
from .common import (
    as_bool,
    as_date,
    as_decimal,
    pagination_meta,
    request_data,
    wants_json,
)


expenses_bp = Blueprint("expenses", __name__, url_prefix="/expenses")


@expenses_bp.route("/", methods=["GET", "POST"])
@login_required
def expense_collection():
    if request.method == "POST":
        return _create_expense()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    statement = db.select(Expense).where(Expense.user_id == current_user.id)
    category = request.args.get("category", "").strip()
    if category:
        statement = statement.where(Expense.category.ilike(category))
    if request.args.get("start_date"):
        statement = statement.where(
            Expense.expense_date >= as_date(request.args["start_date"])
        )
    if request.args.get("end_date"):
        statement = statement.where(
            Expense.expense_date <= as_date(request.args["end_date"])
        )
    pagination = db.paginate(
        statement.order_by(Expense.expense_date.desc()),
        page=max(1, page),
        per_page=max(1, per_page),
        error_out=False,
    )
    total = sum(float(item.amount) for item in pagination.items)
    if wants_json():
        return jsonify(
            {
                "expenses": [item.to_dict() for item in pagination.items],
                "pagination": pagination_meta(pagination),
            }
        )
    return render_template(
        "expenses/index.html",
        page_name="expenses",
        expenses=pagination.items,
        pagination=pagination,
        visible_total=total,
    )


@expenses_bp.get("/summary")
@login_required
def summary():
    start = as_date(request.args.get("start_date", date.today().replace(day=1).isoformat()))
    end = as_date(request.args.get("end_date", date.today().isoformat()))
    expenses = db.session.scalars(
        db.select(Expense).where(
            Expense.user_id == current_user.id,
            Expense.expense_date.between(start, end),
        )
    ).all()
    categories: dict[str, float] = {}
    for item in expenses:
        categories[item.category] = categories.get(item.category, 0) + float(item.amount)
    return jsonify(
        {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "total_expenses": round(sum(categories.values()), 2),
            "by_category": categories,
        }
    )


@expenses_bp.route("/<int:expense_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def expense_detail(expense_id: int):
    expense = db.session.scalar(
        db.select(Expense).where(
            Expense.id == expense_id, Expense.user_id == current_user.id
        )
    )
    if not expense:
        return jsonify({"error": "Expense not found."}), 404
    if request.method == "GET":
        return jsonify({"expense": expense.to_dict()})
    if request.method == "DELETE":
        db.session.delete(expense)
        db.session.commit()
        return jsonify({"message": "Expense deleted."})
    return _apply_expense(expense, request_data())


def _create_expense():
    expense = Expense(user_id=current_user.id)
    return _apply_expense(expense, request_data(), creating=True)


def _apply_expense(expense: Expense, data: dict, creating: bool = False):
    try:
        expense.category = str(data.get("category", expense.category or "")).strip()
        expense.description = str(
            data.get("description", expense.description or "")
        ).strip()
        if not expense.category or not expense.description:
            raise ValueError("Category and description are required.")
        expense.amount = as_decimal(
            data.get("amount", expense.amount), "amount", Decimal("0.01")
        )
        expense.expense_date = as_date(
            data.get("expense_date", expense.expense_date or date.today()),
            "expense date",
        )
        for field in ("payment_method", "vendor_name", "bill_reference"):
            if field in data or creating:
                setattr(expense, field, str(data.get(field, "")).strip() or None)
        if "is_recurring" in data or creating:
            expense.is_recurring = as_bool(data.get("is_recurring", False))
        if creating:
            db.session.add(expense)
        db.session.commit()
        return (
            jsonify(
                {
                    "message": "Expense created." if creating else "Expense updated.",
                    "expense": expense.to_dict(),
                }
            ),
            201 if creating else 200,
        )
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

