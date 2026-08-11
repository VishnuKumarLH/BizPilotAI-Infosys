"""SQLAlchemy data models for core business and agent features."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(db.String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    business_name: Mapped[str] = mapped_column(
        db.String(255), default="StyleHub Men's Fashion", nullable=False
    )
    business_type: Mapped[str] = mapped_column(
        db.String(100), default="Men's Clothing Retail", nullable=False
    )
    business_address: Mapped[str | None] = mapped_column(db.Text)
    business_phone: Mapped[str | None] = mapped_column(db.String(20))
    last_login: Mapped[datetime | None]
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    categories: Mapped[list["Category"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Category(TimestampMixin, db.Model):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_category_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(db.Text)

    user: Mapped[User] = relationship(back_populates="categories")
    products: Mapped[list["Product"]] = relationship(back_populates="category")

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description}


class Product(TimestampMixin, db.Model):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_product_stock_nonnegative"),
        CheckConstraint("purchase_price >= 0", name="ck_product_cost_nonnegative"),
        CheckConstraint("selling_price >= 0", name="ck_product_price_nonnegative"),
        Index("ix_product_user_active", "user_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("categories.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(db.Text)
    sku: Mapped[str] = mapped_column(db.String(50), unique=True, nullable=False)
    size: Mapped[str | None] = mapped_column(db.String(20))
    color: Mapped[str | None] = mapped_column(db.String(50))
    fabric_type: Mapped[str | None] = mapped_column(db.String(100))
    purchase_price: Mapped[Decimal] = mapped_column(db.Numeric(10, 2), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(db.Numeric(10, 2), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(default=0, nullable=False)
    reorder_level: Mapped[int] = mapped_column(default=10, nullable=False)
    max_stock_level: Mapped[int] = mapped_column(default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="products")
    category: Mapped[Category | None] = relationship(back_populates="products")
    sale_items: Mapped[list["SaleItem"]] = relationship(back_populates="product")
    feedback_entries: Mapped[list["CustomerFeedback"]] = relationship(
        back_populates="product"
    )

    @property
    def stock_status(self) -> str:
        if self.stock_quantity == 0:
            return "out_of_stock"
        if self.stock_quantity <= self.reorder_level:
            return "low_stock"
        if self.stock_quantity >= self.max_stock_level:
            return "overstocked"
        return "sufficient"

    @property
    def margin_percent(self) -> float:
        if not self.selling_price:
            return 0.0
        return round(
            float((self.selling_price - self.purchase_price) / self.selling_price * 100),
            2,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category_id": self.category_id,
            "category": self.category.name if self.category else None,
            "description": self.description,
            "sku": self.sku,
            "size": self.size,
            "color": self.color,
            "fabric_type": self.fabric_type,
            "purchase_price": float(self.purchase_price),
            "selling_price": float(self.selling_price),
            "stock_quantity": self.stock_quantity,
            "reorder_level": self.reorder_level,
            "max_stock_level": self.max_stock_level,
            "stock_status": self.stock_status,
            "margin_percent": self.margin_percent,
            "is_active": self.is_active,
        }


class Sale(TimestampMixin, db.Model):
    __tablename__ = "sales"
    __table_args__ = (Index("ix_sale_user_date", "user_id", "sale_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(db.String(50), unique=True, nullable=False)
    customer_name: Mapped[str | None] = mapped_column(db.String(255))
    customer_phone: Mapped[str | None] = mapped_column(db.String(20))
    sale_date: Mapped[date] = mapped_column(default=date.today, nullable=False)
    sale_time: Mapped[time] = mapped_column(
        default=lambda: datetime.now().time().replace(microsecond=0), nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(db.Numeric(10, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        db.Numeric(10, 2), default=0, nullable=False
    )
    final_amount: Mapped[Decimal] = mapped_column(db.Numeric(10, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(db.String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(db.Text)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    items: Mapped[list["SaleItem"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )

    def to_dict(self, include_items: bool = False) -> dict:
        result = {
            "id": self.id,
            "invoice_number": self.invoice_number,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "sale_date": self.sale_date.isoformat(),
            "sale_time": self.sale_time.isoformat(),
            "total_amount": float(self.total_amount),
            "discount_amount": float(self.discount_amount),
            "final_amount": float(self.final_amount),
            "payment_method": self.payment_method,
            "notes": self.notes,
            "item_count": sum(item.quantity for item in self.items),
            "is_active": self.is_active,
        }
        if include_items:
            result["items"] = [item.to_dict() for item in self.items]
        return result


class SaleItem(TimestampMixin, db.Model):
    __tablename__ = "sale_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_sale_item_quantity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(
        db.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("products.id", ondelete="SET NULL")
    )
    product_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(db.Numeric(10, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(db.Numeric(10, 2), nullable=False)

    sale: Mapped[Sale] = relationship(back_populates="items")
    product: Mapped[Product | None] = relationship(back_populates="sale_items")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "total_price": float(self.total_price),
        }


class Expense(TimestampMixin, db.Model):
    __tablename__ = "expenses"
    __table_args__ = (Index("ix_expense_user_date", "user_id", "expense_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(db.String(100), nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(db.Numeric(10, 2), nullable=False)
    expense_date: Mapped[date] = mapped_column(default=date.today, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(db.String(50))
    vendor_name: Mapped[str | None] = mapped_column(db.String(255))
    bill_reference: Mapped[str | None] = mapped_column(db.String(100))
    is_recurring: Mapped[bool] = mapped_column(default=False, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "description": self.description,
            "amount": float(self.amount),
            "expense_date": self.expense_date.isoformat(),
            "payment_method": self.payment_method,
            "vendor_name": self.vendor_name,
            "bill_reference": self.bill_reference,
            "is_recurring": self.is_recurring,
        }


class CustomerFeedback(TimestampMixin, db.Model):
    __tablename__ = "customer_feedback"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_feedback_rating"),
        Index("ix_feedback_user_date", "user_id", "feedback_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    product_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("products.id", ondelete="SET NULL")
    )
    rating: Mapped[int] = mapped_column(nullable=False)
    feedback_text: Mapped[str] = mapped_column(db.Text, nullable=False)
    sentiment: Mapped[str] = mapped_column(db.String(20), nullable=False)
    feedback_date: Mapped[date] = mapped_column(default=date.today, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(default=False, nullable=False)
    resolution_notes: Mapped[str | None] = mapped_column(db.Text)

    product: Mapped[Product | None] = relationship(back_populates="feedback_entries")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else None,
            "rating": self.rating,
            "feedback_text": self.feedback_text,
            "sentiment": self.sentiment,
            "feedback_date": self.feedback_date.isoformat(),
            "is_resolved": self.is_resolved,
            "resolution_notes": self.resolution_notes,
        }


class ChatSession(TimestampMixin, db.Model):
    __tablename__ = "chat_sessions"
    __table_args__ = (Index("ix_session_user_updated", "user_id", "updated_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_title: Mapped[str] = mapped_column(
        db.String(255), default="New Chat", nullable=False
    )
    session_status: Mapped[str] = mapped_column(
        db.String(20), default="active", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def to_dict(self) -> dict:
        last = self.messages[-1] if self.messages else None
        return {
            "id": self.id,
            "session_title": self.session_title,
            "session_status": self.session_status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "preview": last.message_text[:100] if last else "",
        }


class ChatMessage(TimestampMixin, db.Model):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_message_session_created", "session_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        db.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(db.String(20), nullable=False)
    message_text: Mapped[str] = mapped_column(db.Text, nullable=False)
    agent_workflow: Mapped[dict | None] = mapped_column(JSON_TYPE)
    intent: Mapped[str | None] = mapped_column(db.String(50))
    confidence_score: Mapped[Decimal | None] = mapped_column(db.Numeric(3, 2))
    ai_provider: Mapped[str | None] = mapped_column(db.String(20))
    fallback_used: Mapped[bool] = mapped_column(default=False, nullable=False)

    session: Mapped[ChatSession] = relationship(back_populates="messages")
    execution_logs: Mapped[list["AgentExecutionLog"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "message_text": self.message_text,
            "agent_workflow": self.agent_workflow,
            "intent": self.intent,
            "confidence_score": (
                float(self.confidence_score) if self.confidence_score is not None else None
            ),
            "ai_provider": self.ai_provider,
            "fallback_used": self.fallback_used,
            "created_at": self.created_at.isoformat(),
        }


class AgentExecutionLog(TimestampMixin, db.Model):
    __tablename__ = "agent_execution_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[str | None] = mapped_column(db.String(36), index=True)
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(db.String(50), nullable=False)
    execution_order: Mapped[int] = mapped_column(nullable=False)
    input_data: Mapped[dict | None] = mapped_column(JSON_TYPE)
    output_data: Mapped[dict | None] = mapped_column(JSON_TYPE)
    execution_time_ms: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(db.String(20), default="success", nullable=False)
    error_message: Mapped[str | None] = mapped_column(db.Text)

    message: Mapped[ChatMessage | None] = relationship(back_populates="execution_logs")


class BusinessInsight(TimestampMixin, db.Model):
    """Long-term cache for stable business insights referenced by the memory design."""

    __tablename__ = "business_insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    insight_type: Mapped[str] = mapped_column(db.String(50), nullable=False)
    insight_data: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    valid_until: Mapped[datetime | None]


class AgentWorkflowRun(TimestampMixin, db.Model):
    """A compact, queryable record of one coordinated agent workflow."""

    __tablename__ = "agent_workflow_runs"
    __table_args__ = (Index("ix_workflow_user_started", "user_id", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        db.String(36), unique=True, nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("chat_sessions.id", ondelete="SET NULL"), index=True
    )
    user_query: Mapped[str] = mapped_column(db.Text, nullable=False)
    intent: Mapped[str] = mapped_column(db.String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(db.String(20), nullable=False, index=True)
    plan_json: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    analysis_json: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    decision_json: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    lifecycle_events_json: Mapped[list] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    final_response: Mapped[str] = mapped_column(db.Text, default="", nullable=False)
    agents_used_json: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    tools_used_json: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    provider_used: Mapped[str] = mapped_column(
        db.String(30), default="rule_based", nullable=False
    )
    fallback_used: Mapped[bool] = mapped_column(default=False, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(
        db.Numeric(3, 2), default=Decimal("0.00"), nullable=False
    )
    warnings_json: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    errors_json: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    started_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None]
    execution_time_ms: Mapped[int] = mapped_column(default=0, nullable=False)

    def to_dict(self, include_details: bool = False) -> dict:
        result = {
            "workflow_id": self.workflow_id,
            "session_id": self.session_id,
            "user_query": self.user_query,
            "intent": self.intent,
            "status": self.status,
            "agents_used": self.agents_used_json,
            "tools_used": self.tools_used_json,
            "provider_used": self.provider_used,
            "fallback_used": self.fallback_used,
            "confidence": float(self.confidence),
            "warnings": self.warnings_json,
            "errors": self.errors_json,
            "lifecycle_events": self.lifecycle_events_json,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
        }
        if include_details:
            result.update(
                {
                    "plan": self.plan_json,
                    "evidence": self.evidence_json,
                    "analysis": self.analysis_json,
                    "decision": self.decision_json,
                    "final_response": self.final_response,
                }
            )
        return result


class AgentMemory(TimestampMixin, db.Model):
    """Evidence-backed long-term memory retained for future decisions."""

    __tablename__ = "agent_memories"
    __table_args__ = (
        UniqueConstraint(
            "business_id", "memory_type", "memory_key", name="uq_memory_business_key"
        ),
        Index("ix_memory_business_updated", "business_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    memory_type: Mapped[str] = mapped_column(db.String(50), nullable=False, index=True)
    memory_key: Mapped[str] = mapped_column(db.String(120), nullable=False)
    intent: Mapped[str | None] = mapped_column(db.String(50), index=True)
    title: Mapped[str] = mapped_column(db.String(255), nullable=False)
    content: Mapped[str] = mapped_column(db.Text, nullable=False)
    summary: Mapped[str] = mapped_column(db.Text, nullable=False)
    tags: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    source_workflow_id: Mapped[str | None] = mapped_column(db.String(36), index=True)
    importance_score: Mapped[Decimal] = mapped_column(
        db.Numeric(3, 2), default=Decimal("0.50"), nullable=False
    )
    confidence_score: Mapped[Decimal] = mapped_column(
        db.Numeric(3, 2), default=Decimal("0.50"), nullable=False
    )
    usage_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_accessed_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "memory_type": self.memory_type,
            "intent": self.intent,
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "tags": self.tags,
            "source_workflow_id": self.source_workflow_id,
            "importance": float(self.importance_score),
            "confidence": float(self.confidence_score),
            "usage_count": self.usage_count,
            "last_accessed_at": (
                self.last_accessed_at.isoformat() if self.last_accessed_at else None
            ),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "updated_display": self.updated_at.strftime("%d %b %Y, %I:%M %p"),
        }


class ToolCallLog(TimestampMixin, db.Model):
    """Sanitized observability record for one business-tool invocation."""

    __tablename__ = "tool_call_logs"
    __table_args__ = (Index("ix_tool_workflow_created", "workflow_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[str] = mapped_column(db.String(36), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    input_data: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(db.String(20), nullable=False)
    output_summary: Mapped[str] = mapped_column(db.Text, default="", nullable=False)
    error_message: Mapped[str | None] = mapped_column(db.Text)
    execution_time_ms: Mapped[int] = mapped_column(default=0, nullable=False)
