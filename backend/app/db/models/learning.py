from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.db.session import Base

# Allowed LearningContext.type values (validated in code, not DB enum).
TYPE_GOAL = "goal"
TYPE_PREFERENCE = "preference"
TYPE_STRENGTH = "strength"
TYPE_WEAKNESS = "weakness"
TYPE_REPEATED_MISTAKE = "repeated_mistake"
TYPE_TUTOR_CONTEXT = "tutor_context"
TYPE_USER_FACT = "user_fact"
ALLOWED_TYPES = {TYPE_GOAL, TYPE_PREFERENCE, TYPE_STRENGTH, TYPE_WEAKNESS, TYPE_REPEATED_MISTAKE, TYPE_TUTOR_CONTEXT, TYPE_USER_FACT}

# Allowed source values.
SOURCE_CONVERSATION = "conversation"
SOURCE_QUIZ = "quiz"
SOURCE_ASSESSMENT = "assessment"
SOURCE_SYSTEM = "system"


class LearningContext(Base):
    """Persistent learner memory — project-scoped, conservatively extracted.

    Separate from conversation history (Message rows) and from document
    knowledge (DocumentChunk rows). Only rows relevant to the current
    question are ever sent to the LLM.
    """

    __tablename__ = "learning_context"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False, index=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    confidence = Column(Float, default=0.7, nullable=False)
    source = Column(String, nullable=False)
    source_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        # One row per (project, type, concept): re-evidence updates it.
        Index("uq_learning_ctx_concept", "project_id", "type", "concept_id",
              unique=True, postgresql_where=concept_id.is_not(None)),
        # Same event reprocessed never duplicates (message/quiz id key).
        Index("uq_learning_ctx_event", "project_id", "type", "source", "source_id",
              unique=True, postgresql_where=source_id.is_not(None)),
    )


class ConversationSummary(Base):
    """Rolling summary of a chat session's older messages.

    Recent messages are always kept verbatim; only older ones are compressed.
    One row per session.
    """

    __tablename__ = "conversation_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    summary = Column(Text, nullable=False)
    # Last message id covered by the summary (newer ones stay verbatim).
    last_message_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
