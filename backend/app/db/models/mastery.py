from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.db.session import Base


class UserConceptMastery(Base):
    __tablename__ = "user_concept_mastery"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    mastery_score = Column(Integer, default=0, nullable=False)
    last_feedback = Column(Text, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "concept_id", name="uq_user_concept"),)


class QuizHistory(Base):
    __tablename__ = "quiz_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String, nullable=False)
    user_answer = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    evaluator_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class MasteryHistory(Base):
    """Append-only snapshots of Concept.mastery_level over time.

    Written by the same tasks that update mastery (quiz submit, tutor chat
    signal) — never by reads. Growth is derived from these rows; the live
    Concept.mastery_level remains the source of truth for "current".
    Idempotency: (concept_id, source, source_id) is unique so reprocessing
    the same quiz question never creates a duplicate snapshot. Rows with
    NULL source_id (chat/baseline) never collide in Postgres.
    """

    __tablename__ = "mastery_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    mastery = Column(Float, nullable=False)
    source = Column(String, nullable=False)  # quiz | chat | baseline
    source_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # e.g. quiz_question id
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("concept_id", "source", "source_id", name="uq_mastery_history_event"),
    )
