"""Protected external tool proxy routes."""

from flask import Blueprint, jsonify, request
from flask_login import login_required

from ..extensions import cache
from ..services.weather_service import retrieve_weather


tools_bp = Blueprint("tools", __name__, url_prefix="/tools")


@tools_bp.get("/weather")
@login_required
@cache.cached(timeout=1800, query_string=True)
def weather():

    try:
        latitude = request.args.get("latitude", type=float)
        longitude = request.args.get("longitude", type=float)
        if (latitude is None) ^ (longitude is None):
            return jsonify({"error": "Provide both latitude and longitude."}), 400
        return jsonify(
            {
                "weather": retrieve_weather(
                    latitude=latitude,
                    longitude=longitude,
                    location=request.args.get("location"),
                )
            }
        )
    except Exception:
        return jsonify({"error": "Weather data is temporarily unavailable."}), 503

