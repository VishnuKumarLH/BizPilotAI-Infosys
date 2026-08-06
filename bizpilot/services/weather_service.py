"""Open-Meteo integration with a small in-process cache."""

from __future__ import annotations

import time

import requests
from flask import current_app


WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    80: "Rain showers",
    81: "Rain showers",
    82: "Heavy showers",
    95: "Thunderstorm",
}

_cache: dict[str, tuple[float, dict]] = {}


def retrieve_weather(
    latitude: float | None = None,
    longitude: float | None = None,
    location: str | None = None,
) -> dict:
    latitude = latitude if latitude is not None else current_app.config["WEATHER_LATITUDE"]
    longitude = (
        longitude if longitude is not None else current_app.config["WEATHER_LONGITUDE"]
    )
    location = location or current_app.config["WEATHER_LOCATION"]
    cache_key = f"{latitude:.4f},{longitude:.4f}"
    cached = _cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < current_app.config["WEATHER_CACHE_SECONDS"]:
        return {**cached[1], "cached": True}

    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,weather_code",
            "daily": "precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": 1,
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    current = payload.get("current", {})
    daily = payload.get("daily", {})
    code = int(current.get("weather_code", -1))
    result = {
        "location": location,
        "latitude": latitude,
        "longitude": longitude,
        "temperature": current.get("temperature_2m"),
        "apparent_temperature": current.get("apparent_temperature"),
        "condition": WEATHER_CODES.get(code, "Variable conditions"),
        "weather_code": code,
        "rain_probability": (daily.get("precipitation_probability_max") or [None])[0],
        "observed_at": current.get("time"),
        "cached": False,
    }
    _cache[cache_key] = (time.monotonic(), result)
    return result

