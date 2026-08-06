"""Response Agent: deterministic owner-friendly formatting."""

from __future__ import annotations


class ResponseAgent:
    def format(self, decision: dict, retrieval: dict) -> dict:
        findings = [str(item) for item in decision.get("key_findings", [])][:6]
        recommendations = [str(item) for item in decision.get("recommendations", [])][:6]
        reasons = decision.get("reason", [])
        if isinstance(reasons, str):
            reasons = [reasons]
        avoid = decision.get("avoid_actions", [])
        if isinstance(avoid, str):
            avoid = [avoid]
        summary = self._summary(decision["final_decision"], findings)
        return {
            "summary": summary,
            "key_findings": findings,
            "final_decision": str(decision["final_decision"]),
            "recommendations": recommendations,
            "avoid_actions": [str(item) for item in avoid][:5],
            "reasoning": " ".join(str(item) for item in reasons),
            "priority": decision.get("priority", "medium"),
            "confidence": round(float(decision.get("confidence", 0.70)), 2),
            "data_sources": [
                source.replace("_", " ").title()
                for source in retrieval.get("data_sources_used", [])
            ],
            "missing_data": retrieval.get("missing_data", []),
            "ai_provider": decision.get("ai_provider", "rule_based"),
            "fallback_used": bool(decision.get("fallback_used", False)),
        }

    @staticmethod
    def _summary(final_decision: str, findings: list[str]) -> str:
        context = findings[0] if findings else "Available business records were reviewed."
        return f"{context} {final_decision}"

