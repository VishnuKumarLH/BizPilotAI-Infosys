"""API endpoints for automated workflow triggers, job status, and template management."""

from __future__ import annotations

import logging
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from ...extensions import db
from ...models import User, WorkflowJob, WorkflowTemplate
from ...services.scheduler import sync_templates_to_scheduler, trigger_job_now
from ..common import api_key_required

workflow_automation_bp = Blueprint("workflow_automation", __name__)
logger = logging.getLogger(__name__)


@workflow_automation_bp.post("/api/workflows/trigger")
@api_key_required
def trigger_workflow():
    """
    Trigger a workflow execution job asynchronously.
    ---
    tags:
      - Workflow Automation
    parameters:
      - in: header
        name: X-API-Key
        type: string
        required: false
        description: API Key authentication header
      - in: body
        name: body
        required: false
        schema:
          type: object
          properties:
            template_id:
              type: integer
              description: Optional ID of the WorkflowTemplate to execute
            query:
              type: string
              description: Custom business question/prompt to execute
            webhook_url:
              type: string
              description: Optional webhook URL to POST results to upon completion
    responses:
      200:
        description: Workflow job triggered successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            job_id:
              type: string
            status:
              type: string
      400:
        description: Invalid request parameters
      401:
        description: Missing or invalid API Key
    """
    data = request.get_json(silent=True) or {}
    template_id = data.get("template_id")
    query = data.get("query")
    webhook_url = data.get("webhook_url")

    user_id = current_user.id if current_user.is_authenticated else 1
    if template_id:
        template = db.session.get(WorkflowTemplate, template_id)
        if not template:
            return jsonify({"success": False, "error": f"WorkflowTemplate {template_id} not found."}), 404
        user_id = template.user_id

    try:
        job = trigger_job_now(
            template_id=template_id,
            user_id=user_id,
            app=current_app._get_current_object(),
            query_override=query,
            webhook_override=webhook_url,
        )
        return jsonify(
            {
                "success": True,
                "job_id": job.job_id,
                "status": job.status,
                "progress": job.progress,
                "created_at": job.created_at.isoformat(),
            }
        )
    except Exception as exc:
        logger.exception("Failed to trigger workflow job")
        return jsonify({"success": False, "error": f"Failed to trigger job: {str(exc)}"}), 500


@workflow_automation_bp.get("/api/workflows/jobs/<job_id>")
@api_key_required
def get_job_status(job_id: str):
    """
    Retrieve status and result of a specific workflow job.
    ---
    tags:
      - Workflow Automation
    parameters:
      - in: path
        name: job_id
        type: string
        required: true
        description: UUID string of the workflow job
    responses:
      200:
        description: Job status and execution result details
        schema:
          type: object
          properties:
            success:
              type: boolean
            job:
              type: object
      404:
        description: Job not found
    """
    job = db.session.scalar(
        db.select(WorkflowJob).where(WorkflowJob.job_id == job_id)
    )
    if not job:
        return jsonify({"success": False, "error": "Job not found."}), 404

    return jsonify({"success": True, "job": job.to_dict()})


@workflow_automation_bp.get("/api/workflows/templates")
@login_required
def list_templates():
    """List all workflow templates for the authenticated user."""
    templates = db.session.scalars(
        db.select(WorkflowTemplate)
        .where(WorkflowTemplate.user_id == current_user.id)
        .order_by(WorkflowTemplate.created_at.desc())
    ).all()
    return jsonify({"success": True, "templates": [t.to_dict() for t in templates]})


@workflow_automation_bp.post("/api/workflows/templates")
@login_required
def create_template():
    """Create a new workflow template."""
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"success": False, "error": "Template name is required."}), 400

    template = WorkflowTemplate(
        user_id=current_user.id,
        name=name,
        description=data.get("description"),
        trigger_type=data.get("trigger_type", "schedule"),
        agent_sequence=data.get(
            "agent_sequence",
            ["planning_agent", "research_agent", "analysis_decision_agent", "response_agent"],
        ),
        parameters=data.get("parameters", {"query": name}),
        schedule=data.get("schedule"),
        webhook_url=data.get("webhook_url"),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(template)
    db.session.commit()

    try:
        sync_templates_to_scheduler(current_app._get_current_object())
    except Exception:
        logger.exception("Failed to sync scheduler after template creation")

    return jsonify({"success": True, "template": template.to_dict()}), 201


@workflow_automation_bp.delete("/api/workflows/templates/<int:template_id>")
@login_required
def delete_template(template_id: int):
    """Delete a workflow template."""
    template = db.session.scalar(
        db.select(WorkflowTemplate).where(
            WorkflowTemplate.id == template_id,
            WorkflowTemplate.user_id == current_user.id,
        )
    )
    if not template:
        return jsonify({"success": False, "error": "Template not found."}), 404

    db.session.delete(template)
    db.session.commit()

    try:
        sync_templates_to_scheduler(current_app._get_current_object())
    except Exception:
        logger.exception("Failed to sync scheduler after template deletion")

    return jsonify({"success": True, "message": "Workflow template deleted."})
