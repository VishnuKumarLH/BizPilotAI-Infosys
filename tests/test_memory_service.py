from __future__ import annotations

from bizpilot.extensions import db
from bizpilot.models import AgentMemory
from bizpilot.services.memory_service import MemoryService


def test_long_term_memory_upserts_duplicate_business_decision(app):
    with app.app_context():
        service = MemoryService()
        base = {
            "business_id": 1,
            "memory_type": "previous_decision",
            "memory_key": "decision:inventory",
            "intent": "inventory",
            "title": "Inventory decision",
            "content": "Restock Linen Shirt.",
            "summary": "Linen Shirt is below its reorder level.",
            "tags": ["inventory", "low_stock_tool"],
            "source_workflow_id": "workflow-one",
            "importance_score": 0.8,
            "confidence_score": 0.8,
        }
        service.save_long_term_memory(base)
        db.session.commit()
        service.save_long_term_memory(
            {
                **base,
                "content": "Restock Linen Shirt first.",
                "source_workflow_id": "workflow-two",
            }
        )
        db.session.commit()
        rows = db.session.scalars(db.select(AgentMemory)).all()
        assert len(rows) == 1
        assert rows[0].content == "Restock Linen Shirt first."
        assert rows[0].source_workflow_id == "workflow-two"


def test_memory_rejects_secret_like_content(app):
    with app.app_context():
        memory = MemoryService().save_long_term_memory(
            {
                "business_id": 1,
                "memory_type": "business_fact",
                "memory_key": "unsafe",
                "title": "Unsafe",
                "content": "sk-abcdefghijklmnopqrstuvwxyz1234567890",
            }
        )
        assert memory is None
