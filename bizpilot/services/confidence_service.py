"""Transparent confidence scoring for evidence-backed decisions."""

from __future__ import annotations


def calculate_confidence(
    required_tools: list[str],
    tool_results: dict,
    evidence: dict,
    provider_used: str,
    warnings: list[str],
    model_confidence: float | None = None,
) -> float:
    score = 1.0
    contextual = {"conversation_context", "long_term_memory"}
    for tool in required_tools:
        if tool in contextual:
            if not evidence.get(tool):
                score -= 0.15
            continue
        if not tool_results.get(tool, {}).get("success"):
            score -= 0.15
    if not evidence:
        score -= 0.15
    if provider_used == "groq":
        score -= 0.10
    elif provider_used == "rule_based":
        score -= 0.15
    score -= min(0.15, len(warnings) * 0.03)
    score = max(0.0, min(1.0, score))
    if model_confidence is not None:
        try:
            score = min(score, max(0.0, min(1.0, float(model_confidence))))
        except (TypeError, ValueError):
            pass
    return round(score, 2)
