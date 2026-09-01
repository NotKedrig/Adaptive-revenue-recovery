"""
app/db/state/models.py — SQLAlchemy ORM models for AI Revenue Recovery.

Tables:
  - source_documents: one row per ingested raw document (RAG).
  - document_chunks:  one row per chunk produced during ingestion (RAG).
  - customers:        merchant customers with payment profiles.
  - payments:         failed or at-risk payments.
  - recovery_cases:   active/closed recovery cases managing a payment.
  - recovery_attempts: individual retry or notification attempts.
  - recovery_events:  event sourcing / status tracking.
  - audit_logs:       compliance and security audit trail.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    ForeignKey,
    Index,
    JSON,
    Boolean,
    Numeric,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# RAG Knowledge Base (Preserved Infrastructure)
# ---------------------------------------------------------------------------

class SourceDocument(Base):
    __tablename__ = "source_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String(255), nullable=False, unique=True, index=True)
    title = Column(String(512), nullable=False)
    file_path = Column(Text, nullable=False)
    file_hash = Column(String(64), nullable=True)
    char_count = Column(Integer, nullable=True)
    ingested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    chunks = relationship(
        "DocumentChunk",
        back_populates="source_document",
        cascade="all, delete-orphan",
    )

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(String(512), nullable=False, unique=True, index=True)
    doc_id = Column(
        String(255),
        ForeignKey("source_documents.doc_id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index = Column(Integer, nullable=False)
    chunking_strategy = Column(String(64), nullable=False)
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    text_preview = Column(String(256), nullable=True)
    chroma_collection = Column(String(255), nullable=True)
    ingested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    source_document = relationship("SourceDocument", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("doc_id", "chunk_index", "chunking_strategy",
                         name="uq_chunk_doc_index_strategy"),
        Index("idx_chunks_doc_strategy", "doc_id", "chunking_strategy"),
    )


# ---------------------------------------------------------------------------
# Financial Domain Foundation
# ---------------------------------------------------------------------------

class Customer(Base):
    """
    Represents an end-customer who owes a payment.
    """
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(255), nullable=False, unique=True, index=True)
    merchant_id = Column(String(255), nullable=False, index=True)
    
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(255), nullable=True)
    
    preferences = Column(JSON, nullable=True)
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    payments = relationship("Payment", back_populates="customer")


class Payment(Base):
    """
    Represents a payment transaction (failed or at-risk).
    """
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(String(255), nullable=False, unique=True, index=True)
    customer_id = Column(
        String(255),
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Financial fields
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    
    # Context
    payment_method = Column(String(64), nullable=True) # e.g. card, upi, netbanking
    card_network = Column(String(64), nullable=True)
    issuer_bank = Column(String(255), nullable=True)
    
    # Failure specifics
    failure_code = Column(String(64), nullable=True)
    failure_reason = Column(Text, nullable=True)
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    customer = relationship("Customer", back_populates="payments")
    recovery_cases = relationship("RecoveryCase", back_populates="payment")


class RecoveryCase(Base):
    """
    Manages the recovery lifecycle of a single failed payment.
    """
    __tablename__ = "recovery_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(255), nullable=False, unique=True, index=True)
    payment_id = Column(
        String(255),
        ForeignKey("payments.payment_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    status = Column(String(64), nullable=False, default="open") # open, recovered, failed, escalated
    strategy_config = Column(JSON, nullable=True)
    escalation_level = Column(Integer, nullable=False, default=0)
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    payment = relationship("Payment", back_populates="recovery_cases")
    attempts = relationship("RecoveryAttempt", back_populates="case")
    events = relationship("RecoveryEvent", back_populates="case")


class RecoveryAttempt(Base):
    """
    An individual action taken to recover the payment (retry, email, SMS).
    """
    __tablename__ = "recovery_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(
        String(255),
        ForeignKey("recovery_cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    action_type = Column(String(64), nullable=False) # retry, notify_email, notify_sms
    status = Column(String(64), nullable=False, default="pending") # pending, success, failure
    
    request_payload = Column(JSON, nullable=True)
    response_payload = Column(JSON, nullable=True)
    
    attempted_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    case = relationship("RecoveryCase", back_populates="attempts")


class RecoveryEvent(Base):
    """
    Event sourcing log for tracking state changes and agent decisions.
    """
    __tablename__ = "recovery_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(
        String(255),
        ForeignKey("recovery_cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    event_type = Column(String(64), nullable=False) # diagnosis_complete, strategy_planned, safety_flagged
    agent_name = Column(String(64), nullable=False)
    event_data = Column(JSON, nullable=False)
    
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    case = relationship("RecoveryCase", back_populates="events")


class AuditLog(Base):
    """
    Compliance and security audit trail.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(255), nullable=False)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(255), nullable=False)
    details = Column(JSON, nullable=True)
    
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
