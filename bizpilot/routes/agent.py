"""Milestone 3 workflow, history, and memory APIs and pages."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import (
    AgentExecutionLog,
    AgentMemory,
    AgentWorkflowRun,
    ChatMessage,
    ChatSession,
    ToolCallLog,
)
from ..services.memory_service import MemoryService
from ..services.workflow_service import WorkflowService


agent_bp = Blueprint("agent", __name__)
logger = logging.getLogger(__name__)


@agent_bp.post("/api/agent/run")
@login_required
def run_agent_workflow():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "A JSON request body is required."}), 400
    query = str(data.get("query", "")).strip()
    if not query:
        return jsonify({"success": False, "error": "Enter a business question."}), 400
    if len(query) > 2000:
        return jsonify({"success": False, "error": "Keep the question under 2,000 characters."}), 400
    session = None
    if data.get("session_id") is not None:
        session = _owned_session(data["session_id"])
        if not session or session.session_status != "active":
            return jsonify({"success": False, "error": "Chat session not found."}), 404
    try:
        result = WorkflowService().execute(query, current_user.id, session)
        state = result.pop("state")
        response = state["response"]
        return jsonify(
            {
                "success": True,
                "workflow_id": state["workflow_id"],
                "session_id": result["session"]["id"],
                "intent": state["intent"],
                "status": state["status"],
                "decision": state["decision"],
                "final_response": state["final_response"],
                "response": response,
                "agents_used": state["agents_used"],
                "tools_used": state["tools_used"],
                "provider_used": state["provider_used"],
                "fallback_used": state["fallback_used"],
                "confidence": state["confidence"],
                "warnings": state["warnings"],
                "execution_steps": state["execution_trace"],
                "execution_time_ms": state["execution_time_ms"],
            }
        )
    except Exception:
        logger.exception("Agent API workflow failed")
        return jsonify(
            {
                "success": False,
                "error": "BizPilot could not complete the analysis. Please try again.",
            }
        ), 500


@agent_bp.get("/api/agent/workflows")
@login_required
def workflow_collection():
    limit = max(1, min(request.args.get("limit", 20, type=int), 50))
    rows = db.session.scalars(
        db.select(AgentWorkflowRun)
        .where(AgentWorkflowRun.user_id == current_user.id)
        .order_by(AgentWorkflowRun.started_at.desc())
        .limit(limit)
    ).all()
    return jsonify({"success": True, "workflows": [row.to_dict() for row in rows]})


@agent_bp.get("/api/agent/workflows/<workflow_id>")
@login_required
def workflow_detail(workflow_id: str):
    run = _owned_workflow(workflow_id)
    if not run:
        return jsonify({"success": False, "error": "Workflow not found."}), 404
    steps = db.session.scalars(
        db.select(AgentExecutionLog)
        .where(
            AgentExecutionLog.workflow_id == workflow_id,
            AgentExecutionLog.user_id == current_user.id,
        )
        .order_by(AgentExecutionLog.execution_order)
    ).all()
    tools = db.session.scalars(
        db.select(ToolCallLog)
        .where(
            ToolCallLog.workflow_id == workflow_id,
            ToolCallLog.user_id == current_user.id,
        )
        .order_by(ToolCallLog.created_at)
    ).all()
    payload = run.to_dict(include_details=True)
    payload["agent_steps"] = [_step_dict(step) for step in steps]
    payload["tool_calls"] = [_tool_call_dict(tool) for tool in tools]
    return jsonify({"success": True, "workflow": payload})


@agent_bp.get("/api/memory")
@login_required
def memory_collection():
    session_id = request.args.get("session_id", type=int)
    if session_id and not _owned_session(session_id):
        return jsonify({"success": False, "error": "Chat session not found."}), 404
    short_term = MemoryService().get_short_term_context(
        session_id, user_id=current_user.id
    )
    long_term = MemoryService().search_long_term_memory(
        "",
        business_id=current_user.id,
        limit=request.args.get("limit", 20, type=int),
        update_usage=False,
    )
    return jsonify(
        {
            "success": True,
            "session_id": session_id,
            "short_term": short_term,
            "long_term": long_term,
        }
    )


@agent_bp.get("/api/memory/search")
@login_required
def memory_search():
    query = str(request.args.get("q", "")).strip()
    memories = MemoryService().search_long_term_memory(
        query,
        intent=request.args.get("intent") or None,
        business_id=current_user.id,
        limit=request.args.get("limit", 10, type=int),
        update_usage=False,
    )
    return jsonify({"success": True, "query": query, "memories": memories})


@agent_bp.delete("/api/memory/<int:memory_id>")
@login_required
def delete_memory(memory_id: int):
    memory = db.session.scalar(
        db.select(AgentMemory).where(
            AgentMemory.id == memory_id,
            AgentMemory.business_id == current_user.id,
        )
    )
    if not memory:
        return jsonify({"success": False, "error": "Memory not found."}), 404
    db.session.delete(memory)
    db.session.commit()
    return jsonify({"success": True, "message": "Long-term memory deleted."})


@agent_bp.delete("/api/memory/session/<int:session_id>")
@login_required
def clear_session_memory(session_id: int):
    session = _owned_session(session_id)
    if not session:
        return jsonify({"success": False, "error": "Chat session not found."}), 404
    for message in list(session.messages):
        db.session.delete(message)
    session.session_title = "Cleared session"
    db.session.commit()
    return jsonify({"success": True, "message": "Short-term session memory cleared."})


@agent_bp.get("/agent-history")
@login_required
def history_page():
    runs = db.session.scalars(
        db.select(AgentWorkflowRun)
        .where(AgentWorkflowRun.user_id == current_user.id)
        .order_by(AgentWorkflowRun.started_at.desc())
        .limit(50)
    ).all()
    workflow_ids = [run.workflow_id for run in runs]
    details = {workflow_id: {"steps": [], "tools": []} for workflow_id in workflow_ids}
    if workflow_ids:
        for step in db.session.scalars(
            db.select(AgentExecutionLog)
            .where(
                AgentExecutionLog.user_id == current_user.id,
                AgentExecutionLog.workflow_id.in_(workflow_ids),
            )
            .order_by(AgentExecutionLog.execution_order)
        ).all():
            details[step.workflow_id]["steps"].append(_step_dict(step))
        for tool in db.session.scalars(
            db.select(ToolCallLog)
            .where(
                ToolCallLog.user_id == current_user.id,
                ToolCallLog.workflow_id.in_(workflow_ids),
            )
            .order_by(ToolCallLog.created_at)
        ).all():
            details[tool.workflow_id]["tools"].append(_tool_call_dict(tool))
    return render_template(
        "agent_history.html",
        page_name="agent_history",
        workflows=runs,
        workflow_details=details,
    )


@agent_bp.get("/memory")
@login_required
def memory_page():
    query = str(request.args.get("q", "")).strip()
    session_id = request.args.get("session_id", type=int)
    if not session_id:
        session_id = db.session.scalar(
            db.select(ChatSession.id)
            .where(
                ChatSession.user_id == current_user.id,
                ChatSession.session_status == "active",
            )
            .order_by(ChatSession.updated_at.desc())
            .limit(1)
        )
    short_term = MemoryService().get_short_term_context(
        session_id, user_id=current_user.id
    )
    long_term = MemoryService().search_long_term_memory(
        query,
        business_id=current_user.id,
        limit=50,
        update_usage=False,
    )
    return render_template(
        "memory.html",
        page_name="memory",
        short_term=short_term,
        long_term=long_term,
        active_session_id=session_id,
        memory_query=query,
    )


def _owned_session(session_id) -> ChatSession | None:
    try:
        parsed = int(session_id)
    except (TypeError, ValueError):
        return None
    return db.session.scalar(
        db.select(ChatSession).where(
            ChatSession.id == parsed,
            ChatSession.user_id == current_user.id,
        )
    )


def _owned_workflow(workflow_id: str) -> AgentWorkflowRun | None:
    return db.session.scalar(
        db.select(AgentWorkflowRun).where(
            AgentWorkflowRun.workflow_id == workflow_id,
            AgentWorkflowRun.user_id == current_user.id,
        )
    )


def _step_dict(step: AgentExecutionLog) -> dict:
    return {
        "agent_name": step.agent_name,
        "step_order": step.execution_order,
        "input_summary": step.input_data,
        "output_summary": step.output_data,
        "status": step.status,
        "error_message": step.error_message,
        "execution_time_ms": step.execution_time_ms,
        "created_at": step.created_at.isoformat(),
    }


def _tool_call_dict(tool: ToolCallLog) -> dict:
    return {
        "tool_name": tool.tool_name,
        "input": tool.input_data,
        "status": tool.status,
        "output_summary": tool.output_summary,
        "error_message": tool.error_message,
        "execution_time_ms": tool.execution_time_ms,
        "created_at": tool.created_at.isoformat(),
    }
