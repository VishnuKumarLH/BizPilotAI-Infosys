"""Construction of the four-agent LangGraph processing sequence."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .state import AgentWorkflowState


def build_workflow(planning_node, research_node, analysis_node, response_node):
    graph = StateGraph(AgentWorkflowState)
    graph.add_node("planning_agent", planning_node)
    graph.add_node("research_agent", research_node)
    graph.add_node("analysis_decision_agent", analysis_node)
    graph.add_node("response_agent", response_node)
    graph.add_edge(START, "planning_agent")
    graph.add_edge("planning_agent", "research_agent")
    graph.add_edge("research_agent", "analysis_decision_agent")
    graph.add_edge("analysis_decision_agent", "response_agent")
    graph.add_edge("response_agent", END)
    return graph.compile()


def execute_template_workflow(template, user_id: int) -> dict:
    """Execute a LangGraph workflow given a WorkflowTemplate and user_id."""
    from ..agents.coordinator import WorkflowCoordinator

    query = None
    if template and hasattr(template, "parameters") and isinstance(template.parameters, dict):
        query = template.parameters.get("query")
    if not query and hasattr(template, "name"):
        query = f"Execute workflow for template {template.name}"
    if not query:
        query = "Run automated decision workflow"

    coordinator = WorkflowCoordinator()
    return coordinator.run(query=query, user_id=user_id)

