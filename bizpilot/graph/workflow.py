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
