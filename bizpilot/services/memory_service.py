"""Database-backed short-term and long-term memory for coordinated agents."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal

from flask import current_app
from sqlalchemy import or_

from ..extensions import db
from ..models import AgentMemory, ChatMessage


SENSITIVE_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"gsk_[0-9A-Za-z]{20,}"),
    re.compile(r"sk-[0-9A-Za-z_-]{20,}"),
)
STOP_WORDS = {
    "what",
    "when",
    "where",
    "which",
    "with",
    "from",
    "that",
    "this",
    "previously",
    "recommend",
    "recommended",
    "please",
}


class MemoryService:
    def get_short_term_context(
        self, session_id: int | None, limit: int | None = None, user_id: int | None = None
    ) -> list[dict]:
        if not session_id:
            return []
        limit = limit or current_app.config["SHORT_TERM_MEMORY_LIMIT"]
        statement = db.select(ChatMessage).where(ChatMessage.session_id == session_id)
        if user_id is not None:
            statement = statement.where(ChatMessage.user_id == user_id)
        messages = db.session.scalars(
            statement.order_by(ChatMessage.created_at.desc()).limit(max(1, min(limit, 20)))
        ).all()
        return [self._message_context(message) for message in reversed(messages)]

    @staticmethod
    def save_conversation_message(
        session_id: int,
        user_id: int,
        role: str,
        content: str,
        intent: str | None = None,
        **metadata,
    ) -> ChatMessage:
        if role not in {"user", "assistant"}:
            raise ValueError("Conversation role must be user or assistant.")
        message = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            role=role,
            message_text=content.strip(),
            intent=intent,
            **metadata,
        )
        db.session.add(message)
        return message

    def search_long_term_memory(
        self,
        query: str,
        intent: str | None = None,
        business_id: int | None = None,
        limit: int | None = None,
        update_usage: bool = True,
    ) -> list[dict]:
        if business_id is None:
            return []
        limit = limit or current_app.config["LONG_TERM_MEMORY_LIMIT"]
        statement = db.select(AgentMemory).where(
            AgentMemory.business_id == business_id
        )
        if intent:
            statement = statement.where(
                or_(AgentMemory.intent == intent, AgentMemory.intent.is_(None))
            )
        terms = self._keywords(query)
        if terms:
            clauses = []
            for term in terms[:8]:
                pattern = f"%{term}%"
                clauses.extend(
                    [
                        AgentMemory.title.ilike(pattern),
                        AgentMemory.summary.ilike(pattern),
                        AgentMemory.content.ilike(pattern),
                    ]
                )
            statement = statement.where(or_(*clauses))
        memories = db.session.scalars(
            statement.order_by(
                AgentMemory.importance_score.desc(), AgentMemory.updated_at.desc()
            ).limit(max(1, min(limit, 20)))
        ).all()
        if update_usage:
            for memory in memories:
                memory.usage_count += 1
                memory.last_accessed_at = datetime.now(timezone.utc)
        return [memory.to_dict() for memory in memories]

    def save_long_term_memory(self, memory_data: dict) -> AgentMemory | None:
        required = {"business_id", "memory_type", "memory_key", "title", "content"}
        if not required.issubset(memory_data):
            raise ValueError("Long-term memory is missing required fields.")
        content = str(memory_data["content"]).strip()
        summary = str(memory_data.get("summary") or content[:500]).strip()
        if not content or self._contains_secret(content) or self._contains_secret(summary):
            return None
        key = str(memory_data["memory_key"])[:120]
        existing = db.session.scalar(
            db.select(AgentMemory).where(
                AgentMemory.business_id == int(memory_data["business_id"]),
                AgentMemory.memory_type == str(memory_data["memory_type"]),
                AgentMemory.memory_key == key,
            )
        )
        values = {
            "intent": memory_data.get("intent"),
            "title": str(memory_data["title"])[:255],
            "content": content,
            "summary": summary,
            "tags": list(dict.fromkeys(memory_data.get("tags", [])))[:12],
            "source_workflow_id": memory_data.get("source_workflow_id"),
            "importance_score": Decimal(
                str(self._score(memory_data.get("importance_score", 0.7)))
            ),
            "confidence_score": Decimal(
                str(self._score(memory_data.get("confidence_score", 0.7)))
            ),
            "updated_at": datetime.now(timezone.utc),
        }
        if existing:
            for field, value in values.items():
                setattr(existing, field, value)
            return existing
        memory = AgentMemory(
            business_id=int(memory_data["business_id"]),
            memory_type=str(memory_data["memory_type"]),
            memory_key=key,
            **values,
        )
        db.session.add(memory)
        return memory

    @staticmethod
    def update_memory_usage(memory_id: int) -> bool:
        memory = db.session.get(AgentMemory, memory_id)
        if not memory:
            return False
        memory.usage_count += 1
        memory.last_accessed_at = datetime.now(timezone.utc)
        return True

    @staticmethod
    def build_memory_context(short_term: list[dict], long_term: list[dict]) -> dict:
        return {
            "recent_conversation": short_term[-8:],
            "relevant_business_memories": long_term[:5],
        }

    @staticmethod
    def _message_context(message: ChatMessage) -> dict:
        result = {
            "message_id": message.id,
            "session_id": message.session_id,
            "role": message.role,
            "content": message.message_text,
            "intent": message.intent,
            "created_at": message.created_at.isoformat(),
            "created_display": message.created_at.strftime("%d %b %Y, %I:%M %p"),
        }
        if message.role == "assistant" and message.agent_workflow:
            result["decision"] = message.agent_workflow.get("decision", {})
            result["response"] = message.agent_workflow.get("response", {})
            result["workflow_id"] = message.agent_workflow.get("workflow_id") or result[
                "response"
            ].get("workflow_id")
        return result

    @staticmethod
    def _keywords(query: str) -> list[str]:
        return list(
            dict.fromkeys(
                word
                for word in re.findall(r"[a-z0-9]+", query.lower())
                if len(word) >= 3 and word not in STOP_WORDS
            )
        )

    @staticmethod
    def _contains_secret(value: str) -> bool:
        return any(pattern.search(value) for pattern in SENSITIVE_PATTERNS)

    @staticmethod
    def _score(value) -> float:
        try:
            return round(max(0.0, min(1.0, float(value))), 2)
        except (TypeError, ValueError):
            return 0.5
