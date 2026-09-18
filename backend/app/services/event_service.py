"""Durable learning-event emission (durable log, idempotent writes).

Emitters call emit_event() right after committing the fact they describe, with
a stable event_key so retries and duplicate deliveries never double-record.
This function never raises — event logging must never break a user request or
background job.
"""
from loguru import logger
from sqlalchemy.exc import IntegrityError

from app.db.models.event import LearningEvent

# Vocabulary shared with the admin activity feed (app/api/v1/admin.py).
USER_REGISTERED = "user_registered"
SPACE_CREATED = "space_created"
PROJECT_CREATED = "project_created"
MATERIAL_UPLOADED = "material_uploaded"
DOCUMENT_PROCESSED = "document_processed"
QUIZ_COMPLETED = "quiz_completed"
ASSESSMENT_COMPLETED = "assessment_completed"


def owner_of_project(db, project_id):
    """Resolve the owning user_id for a project (project -> space -> owner)."""
    try:
        from app.db.models.project import Project
        from app.db.models.space import Space

        project = db.get(Project, project_id)
        if project is None:
            return None
        space = db.get(Space, project.space_id)
        return space.user_id if space else None
    except Exception:
        return None


def emit_event(db, *, type: str, user_id=None, project_id=None,
               text: str | None = None, event_key: str | None = None) -> str:
    """Append one LearningEvent row. Returns 'recorded' | 'duplicate:*' | 'skipped:*'."""
    try:
        if event_key:
            exists = (
                db.query(LearningEvent.id)
                .filter(LearningEvent.event_key == event_key)
                .first()
            )
            if exists:
                return "duplicate:already-recorded"
        db.add(LearningEvent(
            user_id=user_id,
            project_id=project_id,
            type=type,
            text=(text or "")[:1000] or None,
            event_key=event_key,
        ))
        db.commit()
        return "recorded"
    except IntegrityError:
        db.rollback()
        return "duplicate:race"
    except Exception as e:
        db.rollback()
        logger.warning(f"[events] emit skipped ({type}): {e}")
        return f"skipped:{e}"
