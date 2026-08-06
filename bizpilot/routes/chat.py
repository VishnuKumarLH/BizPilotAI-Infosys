"""Chat sessions backed by the Milestone 3 coordinated workflow."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import ChatMessage, ChatSession
from ..services.workflow_service import WorkflowService


chat_bp = Blueprint("chat", __name__, url_prefix="/chat")
logger = logging.getLogger(__name__)


@chat_bp.post("/send")
@login_required
def send():
    data = request.get_json(silent=True) or {}
    prompt = str(data.get("prompt", "")).strip()
    if not prompt:
        return jsonify({"error": "Enter a business question."}), 400
    if len(prompt) > 2000:
        return jsonify({"error": "Keep the question under 2,000 characters."}), 400

    session = None
    if data.get("session_id"):
        session = _owned_session(data["session_id"])
        if not session or session.session_status != "active":
            return jsonify({"error": "Chat session not found."}), 404
    try:
        result = WorkflowService().execute(prompt, current_user.id, session)
        result.pop("state", None)
        return jsonify(result)
    except Exception:
        logger.exception("Chat workflow failed")
        db.session.rollback()
        return jsonify(
            {
                "error": "BizPilot could not complete the analysis. Please try again.",
                "retryable": True,
            }
        ), 500


@chat_bp.get("/sessions")
@login_required
def sessions():
    rows = db.session.scalars(
        db.select(ChatSession)
        .where(
            ChatSession.user_id == current_user.id,
            ChatSession.session_status == "active",
        )
        .order_by(ChatSession.updated_at.desc())
    ).all()
    return jsonify({"sessions": [session.to_dict() for session in rows]})


@chat_bp.get("/sessions/<int:session_id>")
@login_required
def session_detail(session_id: int):
    session = _owned_session(session_id)
    if not session or session.session_status != "active":
        return jsonify({"error": "Chat session not found."}), 404
    return jsonify(
        {
            "session": session.to_dict(),
            "messages": [message.to_dict() for message in session.messages],
        }
    )


@chat_bp.post("/sessions/<int:session_id>/rename")
@login_required
def rename_session(session_id: int):
    session = _owned_session(session_id)
    if not session:
        return jsonify({"error": "Chat session not found."}), 404
    title = str((request.get_json(silent=True) or {}).get("title", "")).strip()
    if not title:
        return jsonify({"error": "Title is required."}), 400
    session.session_title = title[:255]
    db.session.commit()
    return jsonify({"message": "Chat renamed.", "session": session.to_dict()})


@chat_bp.delete("/sessions/<int:session_id>")
@login_required
def archive_session(session_id: int):
    session = _owned_session(session_id)
    if not session:
        return jsonify({"error": "Chat session not found."}), 404
    session.session_status = "archived"
    db.session.commit()
    return jsonify({"message": "Chat archived."})


@chat_bp.get("/history")
@login_required
def history():
    session_id = request.args.get("session_id", type=int)
    if not session_id:
        return jsonify({"messages": []})
    session = _owned_session(session_id)
    if not session:
        return jsonify({"error": "Chat session not found."}), 404
    messages = session.messages[-10:]
    return jsonify({"messages": [message.to_dict() for message in messages]})


def _owned_session(session_id) -> ChatSession | None:
    try:
        parsed = int(session_id)
    except (TypeError, ValueError):
        return None
    return db.session.scalar(
        db.select(ChatSession).where(
            ChatSession.id == parsed, ChatSession.user_id == current_user.id
        )
    )


