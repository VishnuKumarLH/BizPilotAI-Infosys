"""Run and persist a complete coordinated workflow in one transaction."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from ..agents.coordinator import WorkflowCoordinator
from ..extensions import db
from ..models import (
    AgentExecutionLog,
    AgentWorkflowRun,
    ChatSession,
    ToolCallLog,
)
from .memory_service import MemoryService


logger = logging.getLogger(__name__)


class WorkflowService:
    def __init__(self, coordinator: WorkflowCoordinator | None = None) -> None:
        self.coordinator = coordinator or WorkflowCoordinator()
        self.memory = MemoryService()

    def execute(
        self, query: str, user_id: int, session: ChatSession | None = None
    ) -> dict:
        if session is None:
            session = ChatSession(user_id=user_id, session_title=self._session_title(query))
            db.session.add(session)
            db.session.flush()
        context = self.memory.get_short_term_context(
            session.id, user_id=user_id
        )
        user_message = self.memory.save_conversation_message(
            session.id, user_id, "user", query
        )
        db.session.flush()
        try:
            state = self.coordinator.run(
                query,
                user_id,
                session_id=session.id,
                short_term_context=context,
            )
            workflow = self.coordinator.compatibility_workflow(state)
            response = state["response"]
            assistant = self.memory.save_conversation_message(
                session.id,
                user_id,
                "assistant",
                response["summary"],
                intent=state["intent"],
                agent_workflow=workflow,
                confidence_score=Decimal(str(state["confidence"])),
                ai_provider=state["provider_used"],
                fallback_used=state["fallback_used"],
            )
            db.session.flush()
            run = self._workflow_record(state, session.id, user_id)
            db.session.add(run)
            self._save_agent_logs(state, assistant.id, user_id)
            self._save_tool_logs(state, user_id)
            self._save_decision_memory(state, user_id)
            session.updated_at = datetime.fromisoformat(state["completed_at"])
            db.session.commit()
            return {
                "session": session.to_dict(),
                "message": assistant.to_dict(),
                "response": response,
                "workflow": workflow,
                "state": state,
            }
        except Exception:
            logger.exception("Could not persist coordinated workflow")
            db.session.rollback()
            raise

    @staticmethod
    def _workflow_record(
        state: dict, session_id: int, user_id: int
    ) -> AgentWorkflowRun:
        return AgentWorkflowRun(
            workflow_id=state["workflow_id"],
            user_id=user_id,
            session_id=session_id,
            user_query=state["user_query"],
            intent=state["intent"],
            status=state["status"],
            plan_json=state.get("plan", {}),
            evidence_json=state.get("evidence", {}),
            analysis_json=state.get("analysis", {}),
            decision_json=state.get("decision", {}),
            final_response=state.get("final_response", ""),
            agents_used_json=state.get("agents_used", []),
            tools_used_json=state.get("tools_used", []),
            provider_used=state.get("provider_used", "rule_based"),
            fallback_used=state.get("fallback_used", False),
            confidence=Decimal(str(state.get("confidence", 0))),
            warnings_json=state.get("warnings", []),
            errors_json=state.get("errors", []),
            started_at=datetime.fromisoformat(state["started_at"]),
            completed_at=datetime.fromisoformat(state["completed_at"]),
            execution_time_ms=state.get("execution_time_ms", 0),
        )

    @staticmethod
    def _save_agent_logs(state: dict, message_id: int, user_id: int) -> None:
        for log in state.get("agent_step_logs", []):
            db.session.add(
                AgentExecutionLog(
                    workflow_id=state["workflow_id"],
                    user_id=user_id,
                    message_id=message_id,
                    **log,
                )
            )

    @staticmethod
    def _save_tool_logs(state: dict, user_id: int) -> None:
        for log in state.get("tool_call_logs", []):
            db.session.add(
                ToolCallLog(
                    workflow_id=state["workflow_id"], user_id=user_id, **log
                )
            )

    def _save_decision_memory(self, state: dict, user_id: int) -> None:
        if (
            state.get("intent")
            in {"follow_up", "previous_decision", "unsupported", "calculation"}
            or not state.get("evidence")
            or float(state.get("confidence", 0)) < 0.5
        ):
            return
        response = state["response"]
        self.memory.save_long_term_memory(
            {
                "business_id": user_id,
                "memory_type": "previous_decision",
                "memory_key": f"decision:{state['intent']}",
                "intent": state["intent"],
                "title": f"Latest {state['intent'].replace('_', ' ')} recommendation",
                "content": response["final_decision"],
                "summary": response["summary"][:1000],
                "tags": [state["intent"], *state.get("tools_used", [])],
                "source_workflow_id": state["workflow_id"],
                "importance_score": 0.8,
                "confidence_score": state["confidence"],
            }
        )

    @staticmethod
    def _session_title(query: str) -> str:
        title = " ".join(query.split())
        return title[:57] + "..." if len(title) > 60 else title
