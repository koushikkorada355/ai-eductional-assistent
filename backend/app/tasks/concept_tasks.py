import uuid
from datetime import datetime
from loguru import logger
from app.db.session import SessionLocal
import app.db.base  # noqa: F401
from app.db.models.document import Document, DocumentChunk
from app.db.models.assessment import Concept
from app.db.models.project import Project
from app.db.models.space import Space
from app.schemas.mastery import normalize_concept_name
from app.tasks.celery_app import celery_app
from app.services.analytics_service import record_mastery_snapshot


@celery_app.task(name="concepts.extract", bind=True, max_retries=3)
def extract_concepts_task(self, document_id: str) -> str:
    logger.info(f"[concepts.extract] project lookup for document_id={document_id}")
    db = SessionLocal()
    try:
        try:
            doc_uuid = uuid.UUID(document_id)
        except ValueError:
            logger.error(f"[concepts.extract] invalid document_id={document_id}")
            return "failed:invalid-id"

        document = db.get(Document, doc_uuid)
        if document is None:
            logger.error(f"[concepts.extract] document not found {document_id}")
            return "failed:not-found"

        project_id = document.project_id
        chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == doc_uuid)
            .order_by(DocumentChunk.created_at)
            .limit(10)
            .all()
        )
        sample = "\n".join(c.content[:1500] for c in chunks)[:8000]
        if not sample.strip():
            logger.warning(f"[concepts.extract] no text for document {document_id}")
            return "skipped:empty"

        # Shared utility: exact extraction prompt, no max limit, strict validation.
        from app.ai.concept_extractor import extract_concepts, find_semantic_duplicate

        try:
            items = extract_concepts(sample)
        except Exception as e:
            logger.error(f"[concepts.extract] extraction failed for doc {document_id}: {e}")
            raise

        inserted = 0
        for item in items:
            try:
                clean = normalize_concept_name(item["name"])[:200]
            except ValueError as ve:
                logger.warning(f"[concepts.extract] rejecting non-topic concept {item['name']!r}: {ve}")
                continue
            dupe = find_semantic_duplicate(db, project_id, clean)
            if dupe is not None:
                if not dupe.description and item.get("description"):
                    dupe.description = item["description"][:1000]
                    db.commit()
                continue
            db.add(
                Concept(
                    project_id=project_id,
                    document_id=doc_uuid,
                    name=clean,
                    description=item.get("description", "")[:1000] or None,
                    mastery_level=0.0,
                )
            )
            inserted += 1
        db.commit()
        logger.success(f"[concepts.extract] project_id={project_id} inserted={inserted}")
        return f"ready:{inserted}"
    except Exception as e:
        db.rollback()
        logger.error(f"[concepts.extract] failed doc {document_id}: {e}")
        try:
            raise self.retry(exc=e, countdown=10)
        except self.MaxRetriesExceededError:
            return f"failed:{e}"
    finally:
        db.close()


@celery_app.task(name="mastery.update_from_chat")
def update_mastery_from_chat_task(project_id: str, concept_name: str, confidence_score: float) -> str:
    logger.info(f"[mastery.chat] project_id={project_id} concept={concept_name} score={confidence_score}")
    try:
        clean_name = normalize_concept_name(concept_name)[:200]
    except ValueError as ve:
        logger.warning(f"[mastery.chat] rejecting non-topic concept {concept_name!r}: {ve}")
        return "skipped:invalid-name"
    db = SessionLocal()
    try:
        pid = uuid.UUID(project_id)
        concept = (
            db.query(Concept)
            .filter(Concept.project_id == pid, Concept.name == clean_name)
            .first()
        )
        if concept is None:
            from app.ai.concept_extractor import find_semantic_duplicate

            dupe = find_semantic_duplicate(db, pid, clean_name)
            concept = dupe if dupe is not None else Concept(project_id=pid, name=clean_name, mastery_level=0.0)
            if dupe is None:
                db.add(concept)
                db.flush()
        score = max(0.0, min(100.0, float(confidence_score)))
        old_mastery = float(concept.mastery_level)
        concept.mastery_level = round(old_mastery * 0.7 + score * 0.3, 2)
        concept.last_assessed_at = datetime.utcnow()
        concept_created = concept.created_at
        concept_id, concept_name_saved = concept.id, clean_name
        new_mastery = concept.mastery_level
        db.commit()
        # Growth history (separate transaction; mastery math above unchanged).
        try:
            project = db.get(Project, pid)
            space = db.get(Space, project.space_id) if project else None
            record_mastery_snapshot(
                db,
                user_id=space.user_id if space else None,
                project_id=pid,
                concept_id=concept_id,
                new_mastery=new_mastery,
                source="chat",
                source_id=None,
                previous_mastery=old_mastery,
                baseline_at=concept_created,
            )
        except Exception as he:
            logger.warning(f"[mastery.chat] history skipped project={project_id}: {he}")
        logger.success(f"[mastery.chat] project_id={project_id} concept={concept_name_saved} new={new_mastery}")
        return f"updated:{new_mastery}"
    except Exception as e:
        db.rollback()
        logger.error(f"[mastery.chat] failed project {project_id}: {e}")
        return f"failed:{e}"
    finally:
        db.close()
