"""Dashboard and top-level view routes."""

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required


main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    return render_template("chat.html", page_name="chat")


@main_bp.get("/dashboard")
@login_required
def dashboard():
    return redirect(url_for("main.index"))

