"""Analysis and Decision Agent: compare evidence and choose grounded actions."""

from __future__ import annotations

from .decision import DecisionAgent
from .schemas import AnalysisOutput
from ..graph.state import AgentWorkflowState, require_state_fields
from ..services.confidence_service import calculate_confidence
from ..services.validation_service import validate_analysis


LEGACY_INTENT_BY_CATEGORY = {
    "inventory": "inventory_management",
    "sales": "sales_analysis",
    "expenses": "expense_tracking",
    "profit": "profit_analysis",
    "feedback": "customer_feedback_analysis",
    "marketing": "offer_recommendation",
    "weather": "weather_based_decision",
    "business_performance": "business_performance",
    "general_business": "general_business_advice",
}


class AnalysisDecisionAgent:
    def __init__(self) -> None:
        self.decision_agent = DecisionAgent()

    def run(self, state: AgentWorkflowState) -> dict:
        require_state_fields(state, "intent", "plan", "evidence")
        category = state["intent"]
        if category == "follow_up":
            raw = self._follow_up(state)
        elif category == "previous_decision":
            raw = self._previous_decision(state)
        elif category == "calculation":
            raw = self._calculation(state)
        elif category == "unsupported":
            raw = self._unsupported()
        else:
            raw = self._business_decision(state)

        provider = str(raw.get("ai_provider", "rule_based"))
        warnings = list(state.get("warnings", []))
        provider_errors = raw.pop("provider_errors", [])
        if provider_errors and provider == "rule_based":
            warnings.append(
                "AI providers were unavailable, so verified rule-based analysis was used."
            )
        confidence = calculate_confidence(
            state.get("required_tools", []),
            state.get("tool_results", {}),
            state.get("evidence", {}),
            provider,
            warnings,
            raw.get("confidence"),
        )
        analysis = AnalysisOutput(
            decision=str(raw.get("final_decision", "")),
            confidence=confidence,
            key_findings=[str(item) for item in raw.get("key_findings", [])][:8],
            recommended_actions=[
                str(item) for item in raw.get("recommendations", [])
            ][:8],
            risks=[str(item) for item in raw.get("avoid_actions", [])][:6],
            reasoning=self._as_list(raw.get("reason", []))[:6],
            priority=str(raw.get("priority", "medium")),
        ).model_dump()
        warnings.extend(validate_analysis(analysis, state.get("evidence", {})))
        decision = {
            **analysis,
            "final_decision": analysis["decision"],
            "recommendations": analysis["recommended_actions"],
            "avoid_actions": analysis["risks"],
            "reason": analysis["reasoning"],
            "ai_provider": provider,
            "fallback_used": bool(raw.get("fallback_used", provider == "rule_based")),
        }
        return {
            "analysis": analysis,
            "decision": decision,
            "provider_used": provider,
            "fallback_used": decision["fallback_used"],
            "confidence": confidence,
            "warnings": list(dict.fromkeys(warnings)),
            "agents_used": [
                *state.get("agents_used", []),
                "analysis_decision_agent",
            ],
            "execution_trace": [
                *state.get("execution_trace", []),
                "Analysis and Decision Agent",
            ],
        }

    def _business_decision(self, state: AgentWorkflowState) -> dict:
        coordination = {
            **state["coordination"],
            "intent": LEGACY_INTENT_BY_CATEGORY.get(
                state["intent"], "general_business_advice"
            ),
        }
        retrieval = {
            "retrieved_data": self._legacy_evidence(state["evidence"]),
            "missing_data": state.get("retrieval", {}).get(
                "missing_information", []
            ),
            "data_sources_used": state.get("tools_used", []),
        }
        return self.decision_agent.decide(
            coordination, retrieval, state.get("short_term_context", [])
        )

    @staticmethod
    def _legacy_evidence(evidence: dict) -> dict:
        mapped = {
            "inventory": evidence.get("product_lookup_tool", [])[:10],
            "low_stock": evidence.get("low_stock_tool", [])[:10],
            "sales": evidence.get("sales_summary_tool", {}),
            "expenses": evidence.get("expense_summary_tool", {}),
            "best_sellers": evidence.get("best_selling_product_tool", [])[:10],
            "slow_movers": evidence.get("slow_moving_product_tool", [])[:10],
            "feedback": evidence.get("feedback_retrieval_tool", {}),
            "weather": evidence.get("weather_tool", {}),
        }
        performance = evidence.get("product_performance_tool", {})
        if performance:
            mapped["best_sellers"] = (
                performance.get("best_sellers", mapped["best_sellers"])[:10]
            )
            mapped["slow_movers"] = (
                performance.get("slow_movers", mapped["slow_movers"])[:10]
            )
        out_of_stock = evidence.get("out_of_stock_tool", [])
        if out_of_stock:
            out_ids = {item.get("id") for item in out_of_stock}
            mapped["low_stock"] = [
                *out_of_stock[:5],
                *(item for item in mapped["low_stock"] if item.get("id") not in out_ids),
            ][:10]
        return mapped


    @staticmethod
    def _calculation(state: AgentWorkflowState) -> dict:
        result = state.get("evidence", {}).get("calculator_tool")
        if not result:
            return {
                "key_findings": ["The calculation inputs were missing or invalid."],
                "final_decision": "Provide both revenue and expenses as non-negative numbers.",
                "reason": ["A profit margin needs verified revenue and expense values."],
                "recommendations": [
                    "Try: Calculate profit margin for revenue 50000 and expenses 32000."
                ],
                "avoid_actions": ["Do not estimate a margin from incomplete inputs."],
                "priority": "low",
                "confidence": 0.35,
                "ai_provider": "rule_based",
                "fallback_used": True,
            }
        return {
            "key_findings": [
                f"Revenue is ₹{result['revenue']:,.2f}.",
                f"Expenses are ₹{result['expenses']:,.2f}.",
                f"Estimated profit is ₹{result['estimated_profit']:,.2f}.",
            ],
            "final_decision": (
                f"The estimated profit margin is {result['profit_margin_percent']:.1f}%."
            ),
            "reason": ["Profit margin equals revenue minus expenses, divided by revenue."],
            "recommendations": ["Compare the margin with the business's target margin."],
            "avoid_actions": ["Do not treat this estimate as audited net profit."],
            "priority": "medium",
            "confidence": 0.95,
            "ai_provider": "rule_based",
            "fallback_used": True,
        }

    @staticmethod
    def _follow_up(state: AgentWorkflowState) -> dict:
        context = state.get("short_term_context", [])
        prior = next(
            (
                item
                for item in reversed(context)
                if item.get("role") == "assistant"
                and (item.get("decision") or item.get("response"))
            ),
            None,
        )
        if not prior:
            return AnalysisDecisionAgent._missing_memory()
        decision = prior.get("decision", {})
        response = prior.get("response", {})
        findings = decision.get("key_findings") or response.get("key_findings") or []
        reasons = decision.get("reasoning") or decision.get("reason") or response.get(
            "reasoning", ""
        )
        return {
            "key_findings": findings,
            "final_decision": (
                "I chose that recommendation because "
                + (" ".join(AnalysisDecisionAgent._as_list(reasons)) or "it best matched the recorded evidence.")
            ),
            "reason": AnalysisDecisionAgent._as_list(reasons) or findings,
            "recommendations": decision.get("recommended_actions")
            or response.get("recommendations", []),
            "avoid_actions": decision.get("risks") or response.get("avoid_actions", []),
            "priority": decision.get("priority", "medium"),
            "confidence": min(0.9, float(decision.get("confidence", response.get("confidence", 0.7)))),
            "ai_provider": "rule_based",
            "fallback_used": True,
        }

    @staticmethod
    def _previous_decision(state: AgentWorkflowState) -> dict:
        memories = state.get("long_term_memories", [])
        if not memories:
            return AnalysisDecisionAgent._missing_memory()
        memory = memories[0]
        return {
            "key_findings": [f"Previous memory: {memory.get('summary', memory.get('title'))}"],
            "final_decision": memory.get("content") or memory.get("summary"),
            "reason": [
                f"This was saved from workflow {memory.get('source_workflow_id') or 'history'}."
            ],
            "recommendations": ["Re-run the analysis if stock or sales have changed."],
            "avoid_actions": ["Do not assume an older decision reflects current inventory."],
            "priority": "medium",
            "confidence": float(memory.get("confidence", 0.7)),
            "ai_provider": "rule_based",
            "fallback_used": True,
        }

    @staticmethod
    def _missing_memory() -> dict:
        return {
            "key_findings": ["No matching earlier recommendation was found."],
            "final_decision": "Run a new business analysis so BizPilot can save a supported recommendation.",
            "reason": ["There is no evidence-backed prior decision in the available memory."],
            "recommendations": ["Ask the full business question again."],
            "avoid_actions": ["Do not rely on an unverified recollection."],
            "priority": "low",
            "confidence": 0.35,
            "ai_provider": "rule_based",
            "fallback_used": True,
        }

    @staticmethod
    def _unsupported() -> dict:
        return {
            "key_findings": ["The request is outside BizPilot's business decision scope."],
            "final_decision": "Ask about products, sales, expenses, profit, feedback, promotions, or local weather.",
            "reason": ["BizPilot only answers questions it can ground in connected business data."],
            "recommendations": ["Try: How is my business performing this month?"],
            "avoid_actions": ["Do not use an unsupported answer for a business decision."],
            "priority": "low",
            "confidence": 0.95,
            "ai_provider": "rule_based",
            "fallback_used": True,
        }

    @staticmethod
    def _as_list(value) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        if value:
            return [str(value)]
        return []
