"""Deterministic final checks that keep responses grounded and safe."""

from __future__ import annotations

import re


SECRET_PATTERN = re.compile(
    r"(?:AIza[0-9A-Za-z_-]{20,}|gsk_[0-9A-Za-z]{20,}|sk-[0-9A-Za-z_-]{20,})"
)


def validate_analysis(analysis: dict, evidence: dict) -> list[str]:
    warnings: list[str] = []
    if not str(analysis.get("decision", "")).strip():
        raise ValueError("The analysis did not produce a decision.")
    if not evidence and analysis.get("priority") != "low":
        warnings.append("No business dataset was available; confidence was reduced.")
    confidence = float(analysis.get("confidence", 0))
    if not 0 <= confidence <= 1:
        raise ValueError("Confidence must be between zero and one.")
    serialized = str(analysis)
    if SECRET_PATTERN.search(serialized):
        raise ValueError("The generated response contained sensitive data.")
    if any(marker in serialized for marker in ("Traceback (most recent call last)", "RuntimeError:")):
        raise ValueError("The generated response contained a raw technical exception.")
    profit = evidence.get("profit_calculator_tool") or evidence.get("calculator_tool")
    if isinstance(profit, dict) and {"revenue", "expenses", "estimated_profit"} <= profit.keys():
        expected = round(float(profit["revenue"]) - float(profit["expenses"]), 2)
        if abs(expected - float(profit["estimated_profit"])) > 0.01:
            raise ValueError("Profit evidence is internally inconsistent.")
    return warnings
