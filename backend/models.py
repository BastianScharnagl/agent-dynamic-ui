from sqlalchemy import Column, String, Float, JSON, DateTime, func
from database import Base

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Speichert den serialisierten Gemini-Chatverlauf
    history = Column(JSON, default=list)

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String, primary_key=True)
    recipient = Column(String, nullable=False)
    total_amount = Column(String, nullable=False)
    status = Column(String, default="pending_approval")
    items = Column(JSON, default=list)

    approved_amount = Column(Float, nullable=True)
    approval_date = Column(String, nullable=True)
    cost_center = Column(String, nullable=True)
    approval_notes = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
