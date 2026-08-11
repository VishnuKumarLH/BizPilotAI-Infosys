"""Rule-based Coordinator Agent: understand and classify owner prompts."""

from __future__ import annotations

import re
import logging
from collections import defaultdict
from datetime import datetime, timezone
from time import perf_counter
from typing import Callable
from uuid import uuid4

from .analysis_decision_agent import AnalysisDecisionAgent
from .planning_agent import PlanningAgent
from .research_agent import ResearchAgent
from .response_agent import BusinessResponseAgent
from ..graph.state import AgentWorkflowState
from ..graph.workflow import build_workflow
from ..services.memory_service import MemoryService


logger = logging.getLogger(__name__)


class CoordinatorAgent:
    INTENT_KEYWORDS = {
        "weather_based_decision": {
            "weather": 5,
            "rain": 4,
            "rainy": 4,
            "temperature": 4,
            "hot": 2,
            "cold": 2,
            "climate": 3,
        },
        "offer_recommendation": {
            "offer": 5,
            "promotion": 5,
            "discount": 4,
            "bundle": 4,
            "combo": 4,
            "festival": 3,
            "promote": 3,
        },
        "profit_analysis": {
            "profit": 5,
            "margin": 5,
            "profitable": 4,
            "revenue vs": 4,
            "making money": 4,
        },
        "expense_tracking": {
            "expense": 5,
            "cost": 3,
            "spending": 4,
            "rent": 3,
            "salary": 3,
            "reduce expenses": 5,
        },
        "customer_feedback_analysis": {
            "feedback": 5,
            "rating": 4,
            "review": 4,
            "customer saying": 5,
            "complaint": 4,
            "complain": 4,
            "complaining": 5,
            "satisfied": 3,
        },
        "inventory_management": {
            "inventory": 5,
            "stock": 5,
            "restock": 5,
            "reorder": 4,
            "out of stock": 5,
            "running low": 5,
            "excess": 3,
        },
        "sales_analysis": {
            "sales": 5,
            "selling": 4,
            "sold": 4,
            "best seller": 5,
            "performance": 2,
            "average sale": 4,
            "trend": 3,
        },
        "business_performance": {
            "business": 3,
            "overall": 4,
            "health": 4,
            "top action": 3,
            "focus": 2,
            "biggest problem": 4,
            "performing": 3,
        },
        "general_business_advice": {
            "advice": 4,
            "strategy": 4,
            "improve": 2,
            "should i": 2,
            "recommend": 2,
        },
    }

    AREAS_BY_INTENT = {
        "inventory_management": ["inventory", "sales"],
        "sales_analysis": ["sales", "inventory"],
        "expense_tracking": ["expenses"],
        "profit_analysis": ["sales", "expenses"],
        "offer_recommendation": ["sales", "inventory", "customer_feedback"],
        "customer_feedback_analysis": ["customer_feedback"],
        "weather_based_decision": ["weather", "inventory", "sales"],
        "business_performance": [
            "sales",
            "inventory",
            "expenses",
            "customer_feedback",
        ],
        "general_business_advice": ["sales", "inventory", "expenses"],
    }

    def classify(self, prompt: str) -> dict:
        original = prompt.strip()
        normalized = self._normalize(original)
        lowered = normalized.lower()
        scores: dict[str, int] = defaultdict(int)

        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword, weight in keywords.items():
                if keyword in lowered:
                    scores[intent] += weight

        if not scores:
            intent = "general_business_advice"
            confidence = 0.62
        else:
            ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            intent, top_score = ranked[0]
            second_score = ranked[1][1] if len(ranked) > 1 else 0
            confidence = min(0.98, 0.70 + (top_score * 0.025) + ((top_score - second_score) * 0.02))

        weather_terms = {"weather", "rain", "rainy", "temperature", "climate"}
        requires_weather = any(term in lowered for term in weather_terms)
        areas = list(self.AREAS_BY_INTENT[intent])
        if requires_weather and "weather" not in areas:
            areas.append("weather")

        return {
            "original_prompt": original,
            "intent": intent,
            "business_areas": areas,
            "time_period": self._time_period(lowered),
            "requires_external_tool": requires_weather,
            "requires_weather_data": requires_weather,
            "confidence": round(confidence, 2),
            "normalized_prompt": normalized,
        }

    @staticmethod
    def _normalize(prompt: str) -> str:
        prompt = re.sub(r"\s+", " ", prompt).strip()
        if not prompt:
            return prompt
        return prompt[0].upper() + prompt[1:]

    @staticmethod
    def _time_period(prompt: str) -> str:
        patterns = [
            (r"\blast month\b", "last_month"),
            (r"\blast week\b", "last_week"),
            (r"\bthis month\b|\bmonthly\b", "this_month"),
            (r"\bthis week\b|\bweekly\b", "this_week"),
            (r"\byesterday\b", "yesterday"),
            (r"\btoday\b|\bdaily\b", "today"),
        ]
        for pattern, value in patterns:
            if re.search(pattern, prompt):
                return value
        return "last_30_days"


class WorkflowCoordinator:
    """Create shared state, route the graph, handle failures, and return a trace."""

    STEP_LOG_NAMES = {
        "planning_agent": "planning_agent",
        "research_agent": "research_agent",
        "analysis_decision_agent": "analysis_decision_agent",
        "response_agent": "response_agent",
    }

    def __init__(self) -> None:
        self.classifier = CoordinatorAgent()
        self.memory = MemoryService()
        self.planning = PlanningAgent()
        self.research = ResearchAgent()
        self.analysis = AnalysisDecisionAgent()
        self.response = BusinessResponseAgent()
        self.workflow = build_workflow(
            self._planning_node,
            self._research_node,
            self._analysis_node,
            self._response_node,
        )

    def run(
        self,
        query: str,
        user_id: int,
        session_id: int | None = None,
        short_term_context: list[dict] | None = None,
    ) -> AgentWorkflowState:
        started = perf_counter()
        started_at = datetime.now(timezone.utc)
        workflow_id = str(uuid4())
        logger.info("Workflow %s started", workflow_id)
        context = short_term_context
        if context is None:
            context = self.memory.get_short_term_context(
                session_id, user_id=user_id
            )
        long_term = self.memory.search_long_term_memory(
            query, business_id=user_id, update_usage=True
        )
        coordination_started = perf_counter()
        coordination = self.classifier.classify(query)
        lifecycle = [
            self._lifecycle_event("CREATED", started_at, "Coordinator accepted the request."),
            self._lifecycle_event(
                "PLANNING",
                datetime.now(timezone.utc),
                "Planning Agent selected the required business evidence.",
            ),
        ]
        coordination_log = {
            "agent_name": "coordinator",
            "execution_order": 1,
            "input_data": {"query_length": len(query), "workflow_id": workflow_id},
            "output_data": {
                "legacy_intent": coordination["intent"],
                "business_areas": coordination["business_areas"],
            },
            "execution_time_ms": round(
                (perf_counter() - coordination_started) * 1000
            ),
            "status": "success",
            "error_message": None,
        }
        initial: AgentWorkflowState = {
            "workflow_id": workflow_id,
            "session_id": session_id,
            "user_query": query,
            "user_id": user_id,
            "coordination": coordination,
            "short_term_context": context,
            "long_term_memories": long_term,
            "agents_used": [],
            "tools_used": [],
            "execution_trace": ["Coordinator"],
            "agent_step_logs": [coordination_log],
            "tool_call_logs": [],
            "lifecycle_events": lifecycle,
            "provider_used": "rule_based",
            "fallback_used": False,
            "confidence": 0.0,
            "warnings": [],
            "errors": [],
            "status": "running",
            "started_at": started_at.isoformat(),
        }
        try:
            state: AgentWorkflowState = self.workflow.invoke(initial)
        except Exception as exc:
            logger.exception("Workflow %s failed unexpectedly", workflow_id)
            state = dict(initial)
            state["errors"] = [f"Workflow failed during {type(exc).__name__}."]
            state["warnings"] = [
                "BizPilot could not complete every analysis step."
            ]
            state["response"] = self._emergency_response(workflow_id)
            state["final_response"] = state["response"]["summary"]
        completed_at = datetime.now(timezone.utc)
        state["completed_at"] = completed_at.isoformat()
        state["execution_time_ms"] = round((perf_counter() - started) * 1000)
        if state.get("final_response") and state.get("errors"):
            state["status"] = "partial"
        else:
            state["status"] = "completed" if state.get("final_response") else "failed"
        terminal_status = "COMPLETED" if state["status"] == "completed" else state["status"].upper()
        state["lifecycle_events"] = [
            *state.get("lifecycle_events", []),
            self._lifecycle_event(
                terminal_status,
                completed_at,
                f"Workflow finished with {state['status']} status.",
            ),
        ]
        if state.get("response"):
            state["response"]["execution_time_ms"] = state["execution_time_ms"]
            state["response"]["status"] = state["status"]
        logger.info(
            "Workflow %s completed status=%s in %sms",
            workflow_id,
            state["status"],
            state["execution_time_ms"],
        )
        return state

    def compatibility_workflow(self, state: AgentWorkflowState) -> dict:
        evidence = state.get("evidence", {})
        retrieval = state.get("retrieval", {})
        return {
            "coordinator": state.get("coordination", {}),
            "orchestrator": state.get("plan", {}),
            "retriever": {
                "retrieved_data": AnalysisDecisionAgent._legacy_evidence(evidence),
                "evidence": evidence,
                "tool_results": state.get("tool_results", {}),
                "missing_data": retrieval.get("missing_information", []),
                "data_sources_used": state.get("tools_used", []),
                "retrieval_status": retrieval.get("retrieval_status", "failed"),
            },
            "decision": state.get("decision", {}),
            "response": state.get("response", {}),
        }

    def _planning_node(self, state: AgentWorkflowState) -> dict:
        return self._execute_node(state, "planning_agent", 2, self.planning.run)

    def _research_node(self, state: AgentWorkflowState) -> dict:
        return self._execute_node(state, "research_agent", 3, self.research.run)

    def _analysis_node(self, state: AgentWorkflowState) -> dict:
        return self._execute_node(
            state, "analysis_decision_agent", 4, self.analysis.run
        )

    def _response_node(self, state: AgentWorkflowState) -> dict:
        return self._execute_node(state, "response_agent", 5, self.response.run)

    def _execute_node(
        self,
        state: AgentWorkflowState,
        name: str,
        order: int,
        operation: Callable[[AgentWorkflowState], dict],
    ) -> dict:
        started = perf_counter()
        logger.info("Workflow %s agent %s started", state["workflow_id"], name)
        try:
            output = operation(state)
            status = "success"
            error = None
        except Exception as exc:
            logger.exception(
                "Workflow %s agent %s failed", state["workflow_id"], name
            )
            status = "failed"
            error = type(exc).__name__
            output = self._graceful_node_failure(state, name)
        elapsed = round((perf_counter() - started) * 1000)
        lifecycle_status = {
            "planning_agent": "RESEARCHING",
            "research_agent": "ANALYZING",
            "analysis_decision_agent": "VALIDATING",
            "response_agent": "RESPONDING",
        }[name]
        lifecycle_summary = {
            "planning_agent": "Planning completed; research/tool execution is next.",
            "research_agent": "Research and tool execution completed; analysis is next.",
            "analysis_decision_agent": "Decision validation completed; response is next.",
            "response_agent": "Response Agent prepared the owner-facing answer.",
        }[name]
        log = {
            "agent_name": self.STEP_LOG_NAMES[name],
            "execution_order": order,
            "input_data": {
                "workflow_id": state["workflow_id"],
                "available_fields": sorted(state.keys()),
            },
            "output_data": {
                "updated_fields": sorted(output.keys()),
                "warnings": output.get("warnings", [])[-3:],
            },
            "execution_time_ms": elapsed,
            "status": status,
            "error_message": error,
        }
        output["agent_step_logs"] = [*state.get("agent_step_logs", []), log]
        output["lifecycle_events"] = [
            *state.get("lifecycle_events", []),
            self._lifecycle_event(
                lifecycle_status,
                datetime.now(timezone.utc),
                lifecycle_summary,
            ),
        ]
        logger.info(
            "Workflow %s agent %s completed status=%s in %sms",
            state["workflow_id"],
            name,
            status,
            elapsed,
        )
        return output

    @staticmethod
    def _graceful_node_failure(state: AgentWorkflowState, name: str) -> dict:
        warning = f"{name.replace('_', ' ').title()} could not complete normally."
        common = {
            "warnings": [*state.get("warnings", []), warning],
            "errors": [*state.get("errors", []), f"{name}: failed"],
        }
        if name == "planning_agent":
            return {
                **common,
                "intent": "unsupported",
                "request_category": "unsupported",
                "required_tools": [],
                "plan": {
                    "intent": "unsupported",
                    "objective": "Provide scope guidance",
                    "required_tools": [],
                    "steps": ["Explain supported questions"],
                    "expected_output": "scope_guidance",
                    "tool_parameters": {},
                },
            }
        if name == "research_agent":
            return {
                **common,
                "evidence": {},
                "tool_results": {},
                "tools_used": [],
                "retrieval": {
                    "evidence": {},
                    "tool_results": {},
                    "tools_used": [],
                    "missing_information": state.get("required_tools", []),
                    "retrieval_status": "failed",
                },
            }
        if name == "analysis_decision_agent":
            analysis = {
                "decision": "Review the available business records and try this question again.",
                "confidence": 0.2,
                "key_findings": ["The analysis step could not verify a recommendation."],
                "recommended_actions": ["Retry the request."],
                "risks": ["Available evidence may be incomplete."],
                "reasoning": ["BizPilot does not return unsupported claims."],
                "priority": "low",
            }
            return {
                **common,
                "analysis": analysis,
                "decision": {**analysis, "final_decision": analysis["decision"]},
                "provider_used": "rule_based",
                "fallback_used": True,
                "confidence": 0.2,
            }
        return {
            **common,
            "response": WorkflowCoordinator._emergency_response(state["workflow_id"]),
            "final_response": "BizPilot completed a limited analysis. Please retry the request.",
        }

    @staticmethod
    def _emergency_response(workflow_id: str) -> dict:
        return {
            "summary": "BizPilot completed a limited analysis. Please retry the request.",
            "final_decision": "No unsupported business recommendation was returned.",
            "key_findings": [],
            "recommendations": ["Retry the request in a moment."],
            "recommended_actions": ["Retry the request in a moment."],
            "risks": ["The analysis is incomplete."],
            "avoid_actions": ["Do not act on incomplete analysis."],
            "reasoning": "A workflow step was unavailable.",
            "confidence": 0.0,
            "provider_used": "rule_based",
            "ai_provider": "rule_based",
            "fallback_used": True,
            "agents_used": [],
            "tools_used": [],
            "workflow_id": workflow_id,
            "warnings": ["A workflow step was unavailable."],
            "execution_steps": ["Coordinator"],
        }

    @staticmethod
    def _lifecycle_event(status: str, timestamp: datetime, summary: str) -> dict:
        return {
            "status": status,
            "timestamp": timestamp.isoformat(),
            "summary": summary,
        }
