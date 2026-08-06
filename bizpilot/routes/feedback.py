"""Customer feedback CRUD and sentiment summary."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import CustomerFeedback, Product
from .common import (
    as_bool,
    as_date,
    as_int,
    pagination_meta,
    request_data,
    wants_json,
)


feedback_bp = Blueprint("feedback", __name__, url_prefix="/feedback")


@feedback_bp.route("/", methods=["GET", "POST"])
@login_required
def feedback_collection():
    if request.method == "POST":
        return _create_feedback()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    statement = db.select(CustomerFeedback).where(
        CustomerFeedback.user_id == current_user.id
    )
    if request.args.get("rating", type=int):
        statement = statement.where(
            CustomerFeedback.rating == request.args.get("rating", type=int)
        )
    if request.args.get("sentiment"):
        statement = statement.where(
            CustomerFeedback.sentiment == request.args["sentiment"]
        )
    pagination = db.paginate(
        statement.order_by(CustomerFeedback.feedback_date.desc()),
        page=max(1, page),
        per_page=max(1, per_page),
        error_out=False,
    )
    products = db.session.scalars(
        db.select(Product)
        .where(Product.user_id == current_user.id, Product.is_active.is_(True))
        .order_by(Product.name)
    ).all()
    if wants_json():
        return jsonify(
            {
                "feedback": [item.to_dict() for item in pagination.items],
                "pagination": pagination_meta(pagination),
            }
        )
    return render_template(
        "feedback/index.html",
        page_name="feedback",
        feedback_entries=pagination.items,
        pagination=pagination,
        products=products,
    )


@feedback_bp.get("/summary")
@login_required
def summary():
    entries = db.session.scalars(
        db.select(CustomerFeedback).where(CustomerFeedback.user_id == current_user.id)
    ).all()
    sentiments = {"positive": 0, "neutral": 0, "negative": 0}
    for entry in entries:
        sentiments[entry.sentiment] += 1
    return jsonify(
        {
            "average_rating": round(
                sum(entry.rating for entry in entries) / len(entries), 2
            )
            if entries
            else 0,
            "total_feedback": len(entries),
            "sentiment_distribution": sentiments,
            "unresolved": sum(not entry.is_resolved for entry in entries),
        }
    )


@feedback_bp.route("/<int:feedback_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def feedback_detail(feedback_id: int):
    entry = db.session.scalar(
        db.select(CustomerFeedback).where(
            CustomerFeedback.id == feedback_id,
            CustomerFeedback.user_id == current_user.id,
        )
    )
    if not entry:
        return jsonify({"error": "Feedback not found."}), 404
    if request.method == "GET":
        return jsonify({"feedback": entry.to_dict()})
    if request.method == "DELETE":
        db.session.delete(entry)
        db.session.commit()
        return jsonify({"message": "Feedback deleted."})
    return _apply_feedback(entry, request_data())


def _create_feedback():
    entry = CustomerFeedback(user_id=current_user.id)
    return _apply_feedback(entry, request_data(), creating=True)


def _apply_feedback(entry: CustomerFeedback, data: dict, creating: bool = False):
    try:
        entry.customer_name = str(
            data.get("customer_name", entry.customer_name or "")
        ).strip()
        entry.feedback_text = str(
            data.get("feedback_text", entry.feedback_text or "")
        ).strip()
        if not entry.customer_name or not entry.feedback_text:
            raise ValueError("Customer name and feedback are required.")
        if "rating" in data or creating:
            entry.rating = as_int(data.get("rating"), "rating", 1)
            if entry.rating > 5:
                raise ValueError("Rating cannot exceed 5.")
        entry.sentiment = _sentiment(entry.rating)
        if data.get("product_id") not in {None, "", "null"}:
            product_id = as_int(data["product_id"], "product")
            product = db.session.scalar(
                db.select(Product).where(
                    Product.id == product_id, Product.user_id == current_user.id
                )
            )
            if not product:
                raise ValueError("Select a valid product.")
            entry.product_id = product_id
        elif "product_id" in data:
            entry.product_id = None
        if "feedback_date" in data or creating:
            entry.feedback_date = as_date(
                data.get("feedback_date", date.today()), "feedback date"
            )
        if "is_resolved" in data:
            entry.is_resolved = as_bool(data["is_resolved"])
        if "resolution_notes" in data:
            entry.resolution_notes = str(data["resolution_notes"]).strip() or None
        if creating:
            db.session.add(entry)
        db.session.commit()
        return (
            jsonify(
                {
                    "message": "Feedback created." if creating else "Feedback updated.",
                    "feedback": entry.to_dict(),
                }
            ),
            201 if creating else 200,
        )
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


def _sentiment(rating: int) -> str:
    if rating >= 4:
        return "positive"
    if rating == 3:
        return "neutral"
    return "negative"

