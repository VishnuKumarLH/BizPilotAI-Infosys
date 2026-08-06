"""Reusable prompt templates shared by agent implementations."""

from __future__ import annotations

import json


BUSINESS_GROUNDING_RULES = """
You are a business analyst for the business named in the supplied context.
Use only the retrieved evidence and recent conversation supplied below.
Never invent products, amounts, trends, weather, or customer views.
Connect every important recommendation to a stated fact.
Prefer practical, margin-safe actions for a small-business owner.
""".strip()


DECISION_OUTPUT_SCHEMA = """
Return ONLY this JSON object:
{
  "key_findings": ["fact-backed finding"],
  "final_decision": "clear decision",
  "reason": ["brief evidence-linked reason"],
  "recommendations": ["specific action"],
  "avoid_actions": ["risk or action to avoid"],
  "priority": "high",
  "confidence": 0.85
}
""".strip()


def build_decision_prompt(
    coordination: dict, retrieval: dict, history: list[dict], business_name: str
) -> str:
    """Build the single grounded prompt used by the analysis agent."""

    return f"""
{BUSINESS_GROUNDING_RULES}

Business name: {business_name}
Retrieved evidence:
{json.dumps(retrieval, ensure_ascii=False, default=str)}

Recent conversation context (limited):
{json.dumps(history[-8:], ensure_ascii=False, default=str)}

Owner's question: {coordination['original_prompt']}

{DECISION_OUTPUT_SCHEMA}
""".strip()
