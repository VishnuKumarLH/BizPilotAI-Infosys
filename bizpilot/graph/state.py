"""Typed shared state passed between all specialized agents."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentWorkflowState(TypedDict, total=False):
    workflow_id: str
    session_id: int | None
    user_query: str
    user_id: int
    intent: str
    request_category: str
    coordination: dict[str, Any]
    plan: dict[str, Any]
    required_tools: list[str]
    tool_results: dict[str, Any]
    evidence: dict[str, Any]
    short_term_context: list[dict[str, Any]]
    long_term_memories: list[dict[str, Any]]
    analysis: dict[str, Any]
    decision: dict[str, Any]
    response: dict[str, Any]
    final_response: str
    agents_used: list[str]
    tools_used: list[str]
    execution_trace: list[str]
    agent_step_logs: list[dict[str, Any]]
    tool_call_logs: list[dict[str, Any]]
    provider_used: str
    fallback_used: bool
    confidence: float
    warnings: list[str]
    errors: list[str]
    status: str
    started_at: str
    completed_at: str
    execution_time_ms: int


def require_state_fields(state: AgentWorkflowState, *fields: str) -> None:
    """Fail early with a readable error if an agent receives incomplete state."""

    missing = [field for field in fields if field not in state or state[field] is None]
    if missing:
        raise ValueError(f"Workflow state is missing: {', '.join(missing)}")
