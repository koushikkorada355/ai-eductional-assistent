from sqlalchemy import Column, String, Text, Float, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.db.session import Base


class AIUsage(Base):
    """One row per AI-backed operation (tutor turn, quiz generation /
    evaluation, assignment generation / evaluation, concept extraction).

    Deliberately has no foreign keys: rows are append-only analytics and must
    survive deletion of the user/project they describe. Latency covers the
    whole operation (LLM calls + retries), not a single HTTP request.
    Token/cost metering is not implemented yet — see admin_ai_usage.
    """

    __tablename__ = "ai_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feature = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=True, index=True)  # inception | groq | none | other
    model = Column(String, nullable=True)
    latency_ms = Column(Float, nullable=True)
    success = Column(Boolean, default=True, nullable=False)
    error = Column(Text, nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    project_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    calls = Column(Integer, default=1, nullable=False)  # LLM invokes inside this operation
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
