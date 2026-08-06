"""Application configuration for BizPilot AI."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'bizpilot.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    PRIMARY_AI_PROVIDER = os.getenv("PRIMARY_AI_PROVIDER", "gemini")
    FALLBACK_AI_PROVIDER = os.getenv("FALLBACK_AI_PROVIDER", "groq")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    ENABLE_RULE_BASED_FALLBACK = _as_bool(
        os.getenv("ENABLE_RULE_BASED_FALLBACK"), True
    )
    AI_REQUEST_TIMEOUT = int(os.getenv("AI_REQUEST_TIMEOUT", "30"))
    AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "1"))

    SHORT_TERM_MEMORY_LIMIT = int(os.getenv("SHORT_TERM_MEMORY_LIMIT", "8"))
    LONG_TERM_MEMORY_LIMIT = int(os.getenv("LONG_TERM_MEMORY_LIMIT", "5"))

    WEATHER_LATITUDE = float(os.getenv("WEATHER_LATITUDE", "9.9252"))
    WEATHER_LONGITUDE = float(os.getenv("WEATHER_LONGITUDE", "78.1198"))
    WEATHER_LOCATION = os.getenv("WEATHER_LOCATION", "Madurai")
    WEATHER_CACHE_SECONDS = 1800
    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    GEMINI_API_KEY = ""
    GROQ_API_KEY = ""
    SHORT_TERM_MEMORY_LIMIT = 8
    LONG_TERM_MEMORY_LIMIT = 5
