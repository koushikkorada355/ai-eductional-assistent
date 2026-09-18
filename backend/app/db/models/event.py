from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.db.session import Base


class LearningEvent(Base):
    """Durable, append-only log of meaningful learning lifecycle events.

    Written at the moment the fact occurs (registration, space/project
    creation, upload, document ready/failed, quiz completion, assignment
    submission) — never derived on read. Downstream workflows (concept
    extraction after document_ready, mastery updates after quiz_completed)
    run in the same tasks that emit these rows.

    Idempotency: emitters pass a stable `event_key` (e.g. "quiz:<id>");
    reprocessing the same source returns `duplicate:already-recorded`
    instead of a second row. The UNIQUE constraint tolerates NULL keys, so
    only keyed emissions dedupe — unkeyed rows always insert.
    """

    __tablename__ = "learning_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    project_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    type = Column(String, nullable=False, index=True)
    text = Column(Text, nullable=True)
    event_key = Column(String, nullable=True, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
