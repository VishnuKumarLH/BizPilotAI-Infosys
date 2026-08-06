"""Inventory CRUD API and page."""

from __future__ import annotations

import re
import secrets
from decimal import Decimal

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..models import Category, Product
from .common import (
    as_decimal,
    as_int,
    pagination_meta,
    request_data,
    wants_json,
)


products_bp = Blueprint("products", __name__, url_prefix="/products")


@products_bp.route("/", methods=["GET", "POST"])
@login_required
def product_collection():
    if request.method == "POST":
        return _create_product()

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    statement = db.select(Product).where(
        Product.user_id == current_user.id, Product.is_active.is_(True)
    )
    search = request.args.get("search", "").strip()
    category_id = request.args.get("category", type=int)
    status = request.args.get("status", "").strip()
    if search:
        statement = statement.where(
            db.or_(
                Product.name.ilike(f"%{search}%"),
                Product.sku.ilike(f"%{search}%"),
                Product.color.ilike(f"%{search}%"),
            )
        )
    if category_id:
        statement = statement.where(Product.category_id == category_id)
    if status == "out_of_stock":
        statement = statement.where(Product.stock_quantity == 0)
    elif status == "low_stock":
        statement = statement.where(
            Product.stock_quantity > 0,
            Product.stock_quantity <= Product.reorder_level,
        )
    elif status == "sufficient":
        statement = statement.where(Product.stock_quantity > Product.reorder_level)
    pagination = db.paginate(
        statement.order_by(Product.updated_at.desc()),
        page=max(1, page),
        per_page=max(1, per_page),
        error_out=False,
    )
    categories = db.session.scalars(
        db.select(Category)
        .where(Category.user_id == current_user.id)
        .order_by(Category.name)
    ).all()
    if wants_json():
        return jsonify(
            {
                "products": [item.to_dict() for item in pagination.items],
                "pagination": pagination_meta(pagination),
            }
        )
    return render_template(
        "products/index.html",
        page_name="products",
        products=pagination.items,
        pagination=pagination,
        categories=categories,
    )


@products_bp.get("/low-stock")
@login_required
def low_stock():
    products = db.session.scalars(
        db.select(Product)
        .where(
            Product.user_id == current_user.id,
            Product.is_active.is_(True),
            Product.stock_quantity <= Product.reorder_level,
        )
        .order_by(Product.stock_quantity)
    ).all()
    return jsonify({"products": [product.to_dict() for product in products]})


@products_bp.get("/categories")
@login_required
def categories():
    rows = db.session.scalars(
        db.select(Category)
        .where(Category.user_id == current_user.id)
        .order_by(Category.name)
    ).all()
    return jsonify({"categories": [category.to_dict() for category in rows]})


@products_bp.route("/<int:product_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def product_detail(product_id: int):
    product = _owned_product(product_id)
    if not product:
        return jsonify({"error": "Product not found."}), 404
    if request.method == "GET":
        return jsonify({"product": product.to_dict()})
    if request.method == "DELETE":
        product.is_active = False
        db.session.commit()
        return jsonify({"message": "Product archived."})
    return _update_product(product)


def _create_product():
    data = request_data()
    try:
        name = _required(data, "name")
        category_id = as_int(data.get("category_id"), "category")
        category = db.session.scalar(
            db.select(Category).where(
                Category.id == category_id, Category.user_id == current_user.id
            )
        )
        if not category:
            raise ValueError("Select a valid category.")
        purchase_price = as_decimal(
            data.get("purchase_price"), "purchase price", Decimal("0")
        )
        selling_price = as_decimal(
            data.get("selling_price"), "selling price", Decimal("0")
        )
        if selling_price < purchase_price:
            raise ValueError("Selling price cannot be below purchase price.")
        sku = str(data.get("sku", "")).strip().upper() or _generate_sku(name)
        if db.session.scalar(db.select(Product).where(Product.sku == sku)):
            raise ValueError("SKU already exists.")
        product = Product(
            user_id=current_user.id,
            category_id=category.id,
            name=name,
            description=str(data.get("description", "")).strip() or None,
            sku=sku,
            size=str(data.get("size", "")).strip() or None,
            color=str(data.get("color", "")).strip() or None,
            fabric_type=str(data.get("fabric_type", "")).strip() or None,
            purchase_price=purchase_price,
            selling_price=selling_price,
            stock_quantity=as_int(data.get("stock_quantity", 0), "stock", 0),
            reorder_level=as_int(data.get("reorder_level", 10), "reorder level", 0),
            max_stock_level=as_int(
                data.get("max_stock_level", 100), "maximum stock", 1
            ),
        )
        db.session.add(product)
        db.session.commit()
        return jsonify({"message": "Product created.", "product": product.to_dict()}), 201
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


def _update_product(product: Product):
    data = request_data()
    try:
        for field in ("name", "description", "size", "color", "fabric_type"):
            if field in data:
                setattr(product, field, str(data[field]).strip() or None)
        if not product.name:
            raise ValueError("Product name is required.")
        if "category_id" in data:
            category_id = as_int(data["category_id"], "category")
            category = db.session.scalar(
                db.select(Category).where(
                    Category.id == category_id, Category.user_id == current_user.id
                )
            )
            if not category:
                raise ValueError("Select a valid category.")
            product.category_id = category_id
        for field, label in (
            ("purchase_price", "purchase price"),
            ("selling_price", "selling price"),
        ):
            if field in data:
                setattr(product, field, as_decimal(data[field], label, Decimal("0")))
        for field, label, minimum in (
            ("stock_quantity", "stock", 0),
            ("reorder_level", "reorder level", 0),
            ("max_stock_level", "maximum stock", 1),
        ):
            if field in data:
                setattr(product, field, as_int(data[field], label, minimum))
        if product.selling_price < product.purchase_price:
            raise ValueError("Selling price cannot be below purchase price.")
        db.session.commit()
        return jsonify({"message": "Product updated.", "product": product.to_dict()})
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


def _owned_product(product_id: int) -> Product | None:
    return db.session.scalar(
        db.select(Product).where(
            Product.id == product_id, Product.user_id == current_user.id
        )
    )


def _required(data: dict, field: str) -> str:
    value = str(data.get(field, "")).strip()
    if not value:
        raise ValueError(f"{field.replace('_', ' ').title()} is required.")
    return value


def _generate_sku(name: str) -> str:
    prefix = re.sub(r"[^A-Z0-9]", "", name.upper())[:6] or "ITEM"
    while True:
        sku = f"{prefix}-{secrets.token_hex(2).upper()}"
        if not db.session.scalar(db.select(Product.id).where(Product.sku == sku)):
            return sku

