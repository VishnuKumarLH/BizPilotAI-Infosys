"""APScheduler background service and automated job execution engine."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..extensions import db, scheduler
from ..models import WorkflowJob, WorkflowTemplate, utc_now
from .webhook import trigger_webhook

logger = logging.getLogger(__name__)


def init_scheduler(app) -> None:
    """Initialize and start the background scheduler."""
    if not scheduler.running:
        try:
            scheduler.start()
            logger.info("APScheduler background service started successfully.")
        except Exception:
            logger.exception("Failed to start APScheduler background service.")

    with app.app_context():
        try:
            sync_templates_to_scheduler(app)
        except Exception:
            logger.exception("Failed to sync workflow templates to scheduler during init.")


def sync_templates_to_scheduler(app) -> None:
    """Sync active WorkflowTemplates with schedules to APScheduler."""
    templates = db.session.scalars(
        db.select(WorkflowTemplate).where(
            WorkflowTemplate.is_active.is_(True),
            WorkflowTemplate.schedule.is_not(None),
            WorkflowTemplate.schedule != "",
        )
    ).all()

    current_job_ids = set()
    for template in templates:
        job_id = f"workflow_template_{template.id}"
        current_job_ids.add(job_id)
        trigger = _parse_schedule_trigger(template.schedule)
        if not trigger:
            logger.warning("Invalid schedule expression '%s' for template %s", template.schedule, template.id)
            continue

        scheduler.add_job(
            func=_scheduled_template_runner,
            args=[template.id, app],
            id=job_id,
            name=f"Template: {template.name}",
            trigger=trigger,
            replace_existing=True,
        )
        logger.info("Scheduled template %s (%s) with trigger %s", template.id, template.name, template.schedule)

    # Remove stale template jobs
    for existing_job in scheduler.get_jobs():
        if existing_job.id.startswith("workflow_template_") and existing_job.id not in current_job_ids:
            scheduler.remove_job(existing_job.id)
            logger.info("Removed unscheduled job %s", existing_job.id)


def trigger_job_now(
    template_id: int | None,
    user_id: int,
    app,
    query_override: str | None = None,
    webhook_override: str | None = None,
) -> WorkflowJob:
    """Enqueue a job for immediate background execution and return the WorkflowJob record."""
    job_uuid = str(uuid4())
    query = query_override
    template = None

    if template_id:
        template = db.session.get(WorkflowTemplate, template_id)
        if template:
            if not query:
                query = template.parameters.get("query") or f"Run automated workflow: {template.name}"
            if not webhook_override and template.webhook_url:
                webhook_override = template.webhook_url

    if not query:
        query = "Automated business status and performance check."

    job = WorkflowJob(
        job_id=job_uuid,
        template_id=template_id,
        user_id=user_id,
        status="pending",
        progress=0,
        result={},
        trigger_source="api" if template_id else "manual",
        webhook_url=webhook_override,
        created_at=utc_now(),
    )
    db.session.add(job)
    db.session.commit()

    # Schedule immediate execution in background thread
    scheduler.add_job(
        func=execute_workflow_job,
        args=[job.id, app, query],
        id=f"job_run_{job.job_id}",
        name=f"Execution for job {job.job_id}",
        replace_existing=True,
    )

    return job


def execute_workflow_job(job_db_id: int, app, query: str | None = None) -> None:
    """Background worker executing the LangGraph Workflow for a job record."""
    with app.app_context():
        job = db.session.get(WorkflowJob, job_db_id)
        if not job:
            logger.error("Job record %s not found for execution.", job_db_id)
            return

        started_perf = perf_counter()
        job.status = "running"
        job.progress = 20
        job.started_at = utc_now()
        db.session.commit()

        try:
            from ..agents.coordinator import WorkflowCoordinator

            run_query = query
            if not run_query and job.template and job.template.parameters:
                run_query = job.template.parameters.get("query")
            if not run_query:
                run_query = "Automated business analysis request."

            job.progress = 50
            db.session.commit()

            state = WorkflowCoordinator().run(query=run_query, user_id=job.user_id)

            elapsed_ms = round((perf_counter() - started_perf) * 1000)
            job.execution_time_ms = elapsed_ms
            job.completed_at = utc_now()

            job.result = {
                "workflow_id": state.get("workflow_id"),
                "intent": state.get("coordination", {}).get("intent") or state.get("intent", "general_business_advice"),
                "status": state.get("status", "completed"),
                "decision": state.get("decision", {}),
                "response": state.get("response", {}),
                "final_response": state.get("final_response") or state.get("response", {}).get("summary", ""),
                "agents_used": state.get("agents_used", []),
                "tools_used": state.get("tools_used", []),
                "confidence": state.get("confidence", 0.0),
                "warnings": state.get("warnings", []),
                "errors": state.get("errors", []),
            }

            if state.get("errors") and not state.get("final_response"):
                job.status = "failed"
                job.error_message = "; ".join(state["errors"])
                job.progress = 100
            else:
                job.status = "completed"
                job.progress = 100

            trigger_webhook(job)
            db.session.commit()
            logger.info("Job %s executed successfully status=%s in %sms", job.job_id, job.status, elapsed_ms)

        except Exception as exc:
            db.session.rollback()
            logger.exception("Execution of job %s failed", job.job_id)
            job = db.session.get(WorkflowJob, job_db_id)
            if job:
                job.status = "failed"
                job.progress = 100
                job.error_message = f"Execution error: {str(exc)}"
                job.completed_at = utc_now()
                job.execution_time_ms = round((perf_counter() - started_perf) * 1000)
                trigger_webhook(job)
                db.session.commit()


def _scheduled_template_runner(template_id: int, app) -> None:
    """Callback for APScheduler when a template schedule triggers."""
    with app.app_context():
        template = db.session.get(WorkflowTemplate, template_id)
        if not template or not template.is_active:
            return

        query = template.parameters.get("query") if template.parameters else None
        if not query:
            query = f"Scheduled automated execution for {template.name}"

        job = WorkflowJob(
            job_id=str(uuid4()),
            template_id=template.id,
            user_id=template.user_id,
            status="pending",
            progress=0,
            result={},
            trigger_source="schedule",
            webhook_url=template.webhook_url,
            created_at=utc_now(),
        )
        db.session.add(job)
        db.session.commit()

        execute_workflow_job(job.id, app, query=query)


def _parse_schedule_trigger(schedule_str: str):
    """Parse cron or interval schedule string into APScheduler trigger."""
    s = schedule_str.strip().lower()
    if s == "daily":
        return CronTrigger(hour=9, minute=0)
    if s == "hourly":
        return IntervalTrigger(hours=1)
    if s == "every_5_minutes":
        return IntervalTrigger(minutes=5)
    
    parts = s.split()
    if len(parts) == 5:
        try:
            return CronTrigger.from_crontab(s)
        except Exception:
            pass
    return None
