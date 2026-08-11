"""Shared route helpers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from functools import wraps
from flask import current_app, jsonify, request
from flask_login import current_user


def api_key_required(f):
    """Decorator requiring either an authenticated user session or a valid API key header."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.is_authenticated:
            return f(*args, **kwargs)

        expected_key = current_app.config.get("API_KEY")
        if not expected_key:
            return f(*args, **kwargs)

        provided_key = (
            request.headers.get("X-API-Key")
            or request.headers.get("X-Api-Key")
            or request.args.get("api_key")
        )

        auth_header = request.headers.get("Authorization", "")
        if not provided_key and auth_header.startswith("Bearer "):
            provided_key = auth_header[7:].strip()

        if provided_key and provided_key == expected_key:
            return f(*args, **kwargs)

        return (
            jsonify(
                {
                    "success": False,
                    "error": "Unauthorized. A valid API key or active login session is required.",
                }
            ),
            401,
        )

    return decorated


def request_data() -> dict:
    return request.get_json(silent=True) or request.form.to_dict()



def wants_json() -> bool:
    return request.is_json or request.accept_mimetypes.best == "application/json"


def as_int(value, field: str, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a whole number.") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{field} must be at least {minimum}.")
    return parsed


def as_decimal(value, field: str, minimum: Decimal | None = None) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a valid amount.") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{field} must be at least {minimum}.")
    return parsed.quantize(Decimal("0.01"))


def as_date(value, field: str = "date") -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must use YYYY-MM-DD format.") from exc


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def pagination_meta(pagination) -> dict:
    return {
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }

