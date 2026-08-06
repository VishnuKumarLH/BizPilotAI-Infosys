"""Compatibility facade for the Milestone 3 LangGraph workflow."""

from __future__ import annotations

from .coordinator import WorkflowCoordinator


class AgentManager:
    def __init__(self) -> None:
        self.coordinator = WorkflowCoordinator()

    def run(
        self, prompt: str, user_id: int, history: list[dict] | None = None
    ) -> tuple[dict, dict, list[dict]]:
        state = self.coordinator.run(
            prompt, user_id, short_term_context=history or []
        )
        workflow = self.coordinator.compatibility_workflow(state)
        return state["response"], workflow, state["agent_step_logs"]
