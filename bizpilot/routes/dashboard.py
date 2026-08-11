"""Monitoring dashboard page and aggregated metrics API."""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..models import (
    AgentExecutionLog,
    AgentMemory,
    ToolCallLog,
    WorkflowJob,
)
from .common import api_key_required

dashboard_bp = Blueprint("dashboard", __name__)
logger = logging.getLogger(__name__)


@dashboard_bp.get("/dashboard")
@login_required
def dashboard_page():
    """Render the main observability and monitoring dashboard."""
    return render_template("dashboard.html", page_name="dashboard")


@dashboard_bp.get("/api/dashboard/stats")
@api_key_required
def dashboard_stats():
    """
    Return aggregated statistics, recent jobs, latency metrics, and real-time agent steps.
    ---
    tags:
      - Observability Dashboard
    responses:
      200:
        description: Dashboard metrics and real-time feed stats
    """
    user_id = current_user.id if current_user.is_authenticated else 1

    # 1. Recent Workflow Jobs
    recent_jobs_models = db.session.scalars(
        db.select(WorkflowJob)
        .where(WorkflowJob.user_id == user_id)
        .order_by(WorkflowJob.created_at.desc())
        .limit(20)
    ).all()
    recent_jobs = [job.to_dict() for job in recent_jobs_models]

    # 2. Agent Latency Stats
    agent_latency_rows = db.session.execute(
        db.select(
            AgentExecutionLog.agent_name,
            func.avg(AgentExecutionLog.execution_time_ms).label("avg_latency"),
            func.count(AgentExecutionLog.id).label("call_count"),
        )
        .where(AgentExecutionLog.user_id == user_id)
        .group_by(AgentExecutionLog.agent_name)
    ).all()
    agent_latencies = [
        {
            "agent_name": row.agent_name.replace("_", " ").title(),
            "avg_latency_ms": round(float(row.avg_latency or 0), 1),
            "call_count": int(row.call_count),
        }
        for row in agent_latency_rows
    ]

    # 3. Tool Latency Stats
    tool_latency_rows = db.session.execute(
        db.select(
            ToolCallLog.tool_name,
            func.avg(ToolCallLog.execution_time_ms).label("avg_latency"),
            func.count(ToolCallLog.id).label("call_count"),
        )
        .where(ToolCallLog.user_id == user_id)
        .group_by(ToolCallLog.tool_name)
    ).all()
    tool_latencies = [
        {
            "tool_name": row.tool_name.replace("_", " ").title(),
            "avg_latency_ms": round(float(row.avg_latency or 0), 1),
            "call_count": int(row.call_count),
        }
        for row in tool_latency_rows
    ]

    # 4. Job Success / Status breakdown
    job_status_rows = db.session.execute(
        db.select(
            WorkflowJob.status,
            func.count(WorkflowJob.id).label("count"),
        )
        .where(WorkflowJob.user_id == user_id)
        .group_by(WorkflowJob.status)
    ).all()
    status_counts = {row.status: int(row.count) for row in job_status_rows}
    total_jobs = sum(status_counts.values())
    completed_jobs = status_counts.get("completed", 0)
    failed_jobs = status_counts.get("failed", 0)
    running_jobs = status_counts.get("running", 0) + status_counts.get("pending", 0)

    # 5. Memory breakdown
    memory_type_rows = db.session.execute(
        db.select(
            AgentMemory.memory_type,
            func.count(AgentMemory.id).label("count"),
        )
        .where(AgentMemory.business_id == user_id)
        .group_by(AgentMemory.memory_type)
    ).all()
    memory_stats = [
        {"memory_type": row.memory_type.replace("_", " ").title(), "count": int(row.count)}
        for row in memory_type_rows
    ]
    total_memories = sum(m["count"] for m in memory_stats)

    # 6. Real-time agent step log feed
    latest_steps_models = db.session.scalars(
        db.select(AgentExecutionLog)
        .where(AgentExecutionLog.user_id == user_id)
        .order_by(AgentExecutionLog.created_at.desc())
        .limit(15)
    ).all()
    latest_steps = [
        {
            "id": step.id,
            "agent_name": step.agent_name.replace("_", " ").title(),
            "status": step.status,
            "execution_time_ms": step.execution_time_ms,
            "created_at": step.created_at.strftime("%H:%M:%S"),
            "summary": (step.output_data or {}).get("warnings", ["Step executed"])[-1]
            if isinstance(step.output_data, dict)
            else "Step completed",
        }
        for step in latest_steps_models
    ]

    return jsonify(
        {
            "success": True,
            "summary": {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "running_jobs": running_jobs,
                "success_rate": round(completed_jobs / total_jobs * 100, 1) if total_jobs > 0 else 100.0,
                "total_memories": total_memories,
            },
            "recent_jobs": recent_jobs,
            "agent_latencies": agent_latencies,
            "tool_latencies": tool_latencies,
            "status_counts": status_counts,
            "memory_stats": memory_stats,
            "latest_steps": latest_steps,
        }
    )
