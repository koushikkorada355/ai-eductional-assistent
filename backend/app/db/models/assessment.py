from sqlalchemy import Column, String, Text, Float, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime
from app.db.session import Base


class Concept(Base):
    __tablename__ = "concepts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    # Source attribution: document this concept was first extracted from.
    # Nullable — concepts created before tracking (or via chat) have no source.
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    mastery_level = Column(Float, default=0.0, nullable=False)
    last_assessed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, default="Untitled Quiz", nullable=False)
    goal = Column(Text, nullable=True)
    status = Column(String, default="in_progress", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id = Column(UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True, index=True)
    question_type = Column(String, nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSONB, nullable=True)
    correct_answer = Column(Text, nullable=True)
    user_answer = Column(Text, nullable=True)
    evaluation = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, default="Untitled Assignment", nullable=False)
    prompt = Column(Text, nullable=False, default="")  # Instruction / topic line
    concept_ids = Column(JSONB, nullable=False)  # List of concept ID strings
    status = Column(String, default="draft", nullable=False)  # draft, ready, submitted
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AssignmentQuestion(Base):
    __tablename__ = "assignment_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True, index=True)
    question_text = Column(Text, nullable=False)
    options = Column(JSONB, nullable=False)  # Exactly 4 option strings
    correct_answer = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_response = Column(Text, nullable=False, default="")  # Legacy/compat, unused for MCQ
    answers = Column(JSONB, nullable=True)  # {question_id_str: selected_option}
    score = Column(Float, default=0.0, nullable=False)
    total = Column(Integer, default=0, nullable=False)
    feedback = Column(JSONB, nullable=True)  # {per_question: [...], overall: "..."}
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
