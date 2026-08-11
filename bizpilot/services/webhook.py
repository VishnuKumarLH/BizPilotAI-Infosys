"""Webhook notification service for completed workflow jobs."""

from __future__ import annotations

import logging
import requests
from flask import current_app

logger = logging.getLogger(__name__)


def trigger_webhook(job, override_url: str | None = None) -> bool:
    """Send job execution results to a configured webhook endpoint."""
    target_url = override_url or job.webhook_url or current_app.config.get("WEBHOOK_URL")
    if not target_url:
        logger.debug("No webhook URL configured for job %s", job.job_id)
        return False

    payload = {
        "event": "workflow_job.completed" if job.status == "completed" else "workflow_job.failed",
        "job_id": job.job_id,
        "template_id": job.template_id,
        "user_id": job.user_id,
        "status": job.status,
        "progress": job.progress,
        "result": job.result,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "execution_time_ms": job.execution_time_ms,
    }

    try:
        response = requests.post(
            target_url,
            json=payload,
            headers={"Content-Type": "application/json", "User-Agent": "BizPilot-AI-Webhook/1.0"},
            timeout=10,
        )
        if response.status_code < 300:
            logger.info("Webhook delivered successfully to %s for job %s", target_url, job.job_id)
            job.webhook_status = f"success_{response.status_code}"
            return True
        else:
            logger.warning(
                "Webhook delivered with status %s to %s for job %s",
                response.status_code,
                target_url,
                job.job_id,
            )
            job.webhook_status = f"failed_{response.status_code}"
            return False
    except Exception as exc:
        logger.exception("Webhook delivery failed for job %s to %s", job.job_id, target_url)
        job.webhook_status = f"error_{type(exc).__name__}"
        return False
