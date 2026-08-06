"""Sales transaction CRUD with atomic stock updates."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..models import Product, Sale, SaleItem
from .common import (
    as_date,
    as_decimal,
    as_int,
    pagination_meta,
    request_data,
    wants_json,
)


sales_bp = Blueprint("sales", __name__, url_prefix="/sales")


@sales_bp.route("/", methods=["GET", "POST"])
@login_required
def sale_collection():
    if request.method == "POST":
        return _create_sale()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    statement = db.select(Sale).where(
        Sale.user_id == current_user.id, Sale.is_active.is_(True)
    )
    if request.args.get("start_date"):
        statement = statement.where(Sale.sale_date >= as_date(request.args["start_date"]))
    if request.args.get("end_date"):
        statement = statement.where(Sale.sale_date <= as_date(request.args["end_date"]))
    pagination = db.paginate(
        statement.order_by(Sale.sale_date.desc(), Sale.sale_time.desc()),
        page=max(1, page),
        per_page=max(1, per_page),
        error_out=False,
    )
    products = db.session.scalars(
        db.select(Product)
        .where(
            Product.user_id == current_user.id,
            Product.is_active.is_(True),
            Product.stock_quantity > 0,
        )
        .order_by(Product.name)
    ).all()
    if wants_json():
        return jsonify(
            {
                "sales": [sale.to_dict() for sale in pagination.items],
                "pagination": pagination_meta(pagination),
            }
        )
    return render_template(
        "sales/index.html",
        page_name="sales",
        sales=pagination.items,
        pagination=pagination,
        products=products,
    )


@sales_bp.get("/summary")
@login_required
def summary():
    period = request.args.get("period", "monthly")
    days = {"daily": 0, "weekly": 6, "monthly": 29}.get(period, 29)
    start = date.today() if days == 0 else date.today().fromordinal(date.today().toordinal() - days)
    sales = db.session.scalars(
        db.select(Sale).where(
            Sale.user_id == current_user.id,
            Sale.is_active.is_(True),
            Sale.sale_date >= start,
        )
    ).all()
    revenue = sum(float(sale.final_amount) for sale in sales)
    return jsonify(
        {
            "period": period,
            "total_revenue": round(revenue, 2),
            "total_orders": len(sales),
            "units_sold": sum(item.quantity for sale in sales for item in sale.items),
            "average_order_value": round(revenue / len(sales), 2) if sales else 0,
        }
    )


@sales_bp.route("/<int:sale_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def sale_detail(sale_id: int):
    sale = db.session.scalar(
        db.select(Sale).where(Sale.id == sale_id, Sale.user_id == current_user.id)
    )
    if not sale:
        return jsonify({"error": "Sale not found."}), 404
    if request.method == "GET":
        return jsonify({"sale": sale.to_dict(include_items=True)})
    if request.method == "PUT":
        data = request_data()
        sale.notes = str(data.get("notes", sale.notes or "")).strip() or None
        db.session.commit()
        return jsonify({"message": "Sale notes updated.", "sale": sale.to_dict(True)})
    if not sale.is_active:
        return jsonify({"error": "Sale is already archived."}), 409
    for item in sale.items:
        if item.product and item.product.user_id == current_user.id:
            item.product.stock_quantity += item.quantity
    sale.is_active = False
    db.session.commit()
    return jsonify({"message": "Sale archived and stock restored."})


def _create_sale():
    data = request.get_json(silent=True) or {}
    items_data = data.get("items")
    if not isinstance(items_data, list) or not items_data:
        return jsonify({"error": "Add at least one sale item."}), 400
    try:
        prepared: list[tuple[Product, int, Decimal]] = []
        total = Decimal("0")
        seen: set[int] = set()
        for item_data in items_data:
            product_id = as_int(item_data.get("product_id"), "product")
            quantity = as_int(item_data.get("quantity"), "quantity", 1)
            if product_id in seen:
                raise ValueError("Each product may appear only once per sale.")
            seen.add(product_id)
            product = db.session.scalar(
                db.select(Product)
                .where(
                    Product.id == product_id,
                    Product.user_id == current_user.id,
                    Product.is_active.is_(True),
                )
                .with_for_update()
            )
            if not product:
                raise ValueError("One of the selected products is unavailable.")
            if product.stock_quantity < quantity:
                raise ValueError(
                    f"Only {product.stock_quantity} unit(s) of {product.name} are available."
                )
            line_total = (product.selling_price * quantity).quantize(Decimal("0.01"))
            prepared.append((product, quantity, line_total))
            total += line_total
        discount = as_decimal(data.get("discount_amount", 0), "discount", Decimal("0"))
        if discount > total:
            raise ValueError("Discount cannot exceed the sale total.")
        invoice = _invoice_number()
        sale = Sale(
            user_id=current_user.id,
            invoice_number=invoice,
            customer_name=str(data.get("customer_name", "")).strip() or "Walk-in Customer",
            customer_phone=str(data.get("customer_phone", "")).strip() or None,
            sale_date=as_date(data.get("sale_date", date.today().isoformat()), "sale date"),
            sale_time=datetime.now().time().replace(microsecond=0),
            total_amount=total,
            discount_amount=discount,
            final_amount=total - discount,
            payment_method=str(data.get("payment_method", "UPI")).strip(),
            notes=str(data.get("notes", "")).strip() or None,
        )
        db.session.add(sale)
        db.session.flush()
        for product, quantity, line_total in prepared:
            product.stock_quantity -= quantity
            db.session.add(
                SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    product_name=product.name,
                    quantity=quantity,
                    unit_price=product.selling_price,
                    total_price=line_total,
                )
            )
        db.session.commit()
        return jsonify({"message": "Sale recorded.", "sale": sale.to_dict(True)}), 201
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


def _invoice_number() -> str:
    today_prefix = datetime.now().strftime("INV-%Y%m%d")
    count = db.session.scalar(
        db.select(func.count(Sale.id)).where(Sale.invoice_number.like(f"{today_prefix}-%"))
    )
    return f"{today_prefix}-{int(count or 0) + 1:03d}"

