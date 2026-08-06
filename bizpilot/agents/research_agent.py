"""Research Agent: execute the plan and return structured, genuine evidence."""

from __future__ import annotations

import json

from .schemas import RetrievalOutput
from ..graph.state import AgentWorkflowState, require_state_fields
from ..tools import ToolRegistry


class ResearchAgent:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry()

    def run(self, state: AgentWorkflowState) -> dict:
        require_state_fields(state, "plan", "user_id", "required_tools")
        evidence: dict = {}
        results: dict = {}
        tools_used: list[str] = []
        missing: list[str] = []
        warnings = list(state.get("warnings", []))
        call_logs = list(state.get("tool_call_logs", []))
        params_by_tool = state["plan"].get("tool_parameters", {})

        for tool_name in state["required_tools"]:
            if tool_name == "conversation_context":
                context = state.get("short_term_context", [])
                evidence[tool_name] = context
                if not context:
                    missing.append(tool_name)
                continue
            if tool_name == "long_term_memory":
                memories = state.get("long_term_memories", [])
                evidence[tool_name] = memories
                if not memories:
                    missing.append(tool_name)
                continue

            parameters = dict(params_by_tool.get(tool_name, {}))
            if tool_name == "profit_calculator_tool":
                sales = evidence.get("sales_summary_tool", {})
                expenses = evidence.get("expense_summary_tool", {})
                parameters.update(
                    {
                        "revenue": sales.get("total_revenue", 0),
                        "expenses": expenses.get("total_expenses", 0),
                    }
                )
            result, tool_log = self.registry.execute(
                tool_name, state["user_id"], parameters
            )
            tools_used.append(tool_name)
            results[tool_name] = result
            call_logs.append(tool_log)
            if result["success"]:
                evidence[tool_name] = self._deduplicate(result["data"])
            else:
                missing.append(tool_name)
                warnings.append(f"{tool_name.replace('_', ' ')} was unavailable.")

        status = "complete"
        if missing and evidence:
            status = "partial"
        elif missing:
            status = "failed"
        retrieval = RetrievalOutput(
            evidence=evidence,
            tool_results=results,
            tools_used=tools_used,
            missing_information=missing,
            retrieval_status=status,
        ).model_dump()
        return {
            "tool_results": results,
            "evidence": evidence,
            "tools_used": tools_used,
            "retrieval": retrieval,
            "warnings": warnings,
            "tool_call_logs": call_logs,
            "agents_used": [*state.get("agents_used", []), "research_agent"],
            "execution_trace": [
                *state.get("execution_trace", []),
                "Research and Retrieval Agent",
            ],
        }

    @staticmethod
    def _deduplicate(value):
        if not isinstance(value, list):
            return value
        unique = []
        seen: set[str] = set()
        for item in value:
            marker = json.dumps(item, sort_keys=True, default=str)
            if marker not in seen:
                seen.add(marker)
                unique.append(item)
        return unique
