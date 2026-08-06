"""Gemini → Groq → rules provider chain for the Decision Agent only."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import requests
from flask import current_app


@dataclass
class ProviderFailure(Exception):
    message: str
    retryable: bool = True
    configuration_error: bool = False

    def __str__(self) -> str:
        return self.message


class AIService:
    REQUIRED_KEYS = {
        "key_findings",
        "final_decision",
        "reason",
        "recommendations",
        "avoid_actions",
        "priority",
        "confidence",
    }

    def analyze(self, prompt: str) -> tuple[dict | None, str | None, list[str]]:
        errors: list[str] = []
        primary = current_app.config["PRIMARY_AI_PROVIDER"].lower()
        fallback = current_app.config["FALLBACK_AI_PROVIDER"].lower()
        providers = [primary]
        if fallback != primary:
            providers.append(fallback)

        for provider_index, provider in enumerate(providers):
            key = current_app.config.get(f"{provider.upper()}_API_KEY", "")
            if not key:
                errors.append(f"{provider}: API key not configured")
                continue

            attempts = current_app.config["AI_MAX_RETRIES"] + 1 if provider_index == 0 else 1
            for _ in range(attempts):
                try:
                    raw = self._call_provider(provider, key, prompt)
                    decision = self._parse_and_validate(raw)
                    return decision, provider, errors
                except ProviderFailure as exc:
                    errors.append(f"{provider}: {exc}")
                    if exc.configuration_error or not exc.retryable:
                        break

        return None, None, errors

    def _call_provider(self, provider: str, api_key: str, prompt: str) -> str:
        try:
            if provider == "gemini":
                return self._call_gemini(api_key, prompt)
            if provider == "groq":
                return self._call_groq(api_key, prompt)
            raise ProviderFailure(f"Unsupported provider '{provider}'", False, True)
        except requests.Timeout as exc:
            raise ProviderFailure("request timed out", retryable=True) from exc
        except requests.ConnectionError as exc:
            raise ProviderFailure("connection failed", retryable=True) from exc
        except requests.RequestException as exc:
            raise ProviderFailure("request failed", retryable=False) from exc

    def _call_gemini(self, api_key: str, prompt: str) -> str:
        model = current_app.config["GEMINI_MODEL"]
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            },
            timeout=current_app.config["AI_REQUEST_TIMEOUT"],
        )
        self._check_response(response, "Gemini")
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderFailure("empty or malformed response") from exc

    def _call_groq(self, api_key: str, prompt: str) -> str:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": current_app.config["GROQ_MODEL"],
                "messages": [
                    {
                        "role": "system",
                        "content": "Return only valid JSON grounded in the supplied business data.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=current_app.config["AI_REQUEST_TIMEOUT"],
        )
        self._check_response(response, "Groq")
        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderFailure("empty or malformed response") from exc

    @staticmethod
    def _check_response(response: requests.Response, label: str) -> None:
        if response.ok:
            return
        if response.status_code in {401, 403}:
            raise ProviderFailure(
                f"{label} credentials are invalid", retryable=False, configuration_error=True
            )
        if response.status_code in {400, 404}:
            raise ProviderFailure(
                f"{label} model or request configuration is invalid",
                retryable=False,
                configuration_error=True,
            )
        retryable = response.status_code in {429, 500, 502, 503, 504}
        raise ProviderFailure(
            f"{label} request failed with HTTP {response.status_code}",
            retryable=retryable,
        )

    def _parse_and_validate(self, raw: str) -> dict:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        try:
            decision = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            # One conservative repair handles providers that surround valid JSON
            # with a short explanatory sentence. Further repair is intentionally
            # avoided so malformed values cannot enter the workflow state.
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start < 0 or end <= start:
                raise ProviderFailure("invalid JSON response") from exc
            try:
                decision = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError as repair_exc:
                raise ProviderFailure("invalid JSON response") from repair_exc
        if not isinstance(decision, dict) or not self.REQUIRED_KEYS.issubset(decision):
            raise ProviderFailure("JSON response is missing required decision fields")
        for field in ("key_findings", "reason", "recommendations", "avoid_actions"):
            if not isinstance(decision[field], list):
                raise ProviderFailure(f"decision field '{field}' must be a list")
        if not isinstance(decision["final_decision"], str) or not decision[
            "final_decision"
        ].strip():
            raise ProviderFailure("final decision is invalid")
        if decision["priority"] not in {"high", "medium", "low"}:
            raise ProviderFailure("priority is invalid")
        try:
            decision["confidence"] = max(0.0, min(1.0, float(decision["confidence"])))
        except (TypeError, ValueError) as exc:
            raise ProviderFailure("confidence score is invalid") from exc
        return decision
