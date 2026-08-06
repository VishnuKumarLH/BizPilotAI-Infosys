"""Registration, login, logout, and profile endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, flash, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from ..extensions import db
from ..models import Category, User
from .common import request_data, wants_json


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

DEFAULT_CATEGORIES = {
    "Formal Shirts": "Office wear and business meetings",
    "Casual Shirts": "Daily wear and outings",
    "T-Shirts": "Casual, sports, and lounging",
    "Pants & Trousers": "Formal and casual bottoms",
    "Jeans": "Denim wear",
    "Traditional Wear": "Kurtas, dhotis, and veshtis",
    "Accessories": "Belts, wallets, ties, and cufflinks",
}


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if not _is_submission():
        return render_template("auth/register.html")

    data = request_data()
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    confirm = str(data.get("confirm_password", password))
    business_name = str(data.get("business_name", "")).strip()

    errors = []
    if len(username) < 2:
        errors.append("Username must be at least 2 characters.")
    if "@" not in email or len(email) > 255:
        errors.append("Enter a valid email address.")
    if len(password) < 8:
        errors.append("Password must contain at least 8 characters.")
    if password != confirm:
        errors.append("Passwords do not match.")
    exists = db.session.scalar(
        db.select(User).where(
            db.or_(func.lower(User.email) == email, func.lower(User.username) == username.lower())
        )
    )
    if exists:
        errors.append("An account with that username or email already exists.")

    if errors:
        if wants_json():
            return jsonify({"errors": errors}), 400
        for error in errors:
            flash(error, "danger")
        return render_template("auth/register.html", form=data), 400

    user = User(
        username=username,
        email=email,
        business_name=business_name or "StyleHub Men's Fashion",
        business_address=str(data.get("business_address", "")).strip() or None,
        business_phone=str(data.get("business_phone", "")).strip() or None,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add_all(
        [
            Category(user_id=user.id, name=name, description=description)
            for name, description in DEFAULT_CATEGORIES.items()
        ]
    )
    db.session.commit()
    login_user(user)
    if wants_json():
        return jsonify({"message": "Account created.", "user": _profile(user)}), 201
    flash("Welcome to BizPilot AI. Your account is ready.", "success")
    return redirect(url_for("main.index"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if not _is_submission():
        return render_template("auth/login.html")

    data = request_data()
    identifier = str(data.get("email") or data.get("username") or "").strip().lower()
    password = str(data.get("password", ""))
    user = db.session.scalar(
        db.select(User).where(
            db.or_(
                func.lower(User.email) == identifier,
                func.lower(User.username) == identifier,
            )
        )
    )
    if not user or not user.check_password(password) or not user.is_active:
        message = "Invalid email or password."
        if wants_json():
            return jsonify({"error": message}), 401
        flash(message, "danger")
        return render_template("auth/login.html", email=identifier), 401

    user.last_login = datetime.now(timezone.utc)
    db.session.commit()
    login_user(user, remember=bool(data.get("remember")))
    if wants_json():
        return jsonify({"message": "Signed in.", "user": _profile(user)})
    return redirect(url_for("main.index"))


@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    if wants_json():
        return jsonify({"message": "Signed out."})
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.get("/profile")
@login_required
def profile():
    return jsonify({"user": _profile(current_user)})


def _profile(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "business_name": user.business_name,
        "business_type": user.business_type,
        "business_address": user.business_address,
        "business_phone": user.business_phone,
    }


def _is_submission() -> bool:
    from flask import request

    return request.method == "POST"

