import json
import uuid
from datetime import datetime
from loguru import logger
from app.db.session import SessionLocal
import app.db.base  # noqa: F401
from app.db.models.document import Document, DocumentChunk
from app.db.models.assessment import Concept
from app.schemas.quiz import ConceptList
from app.tasks.celery_app import celery_app
from app.ai.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage


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

        llm = get_llm()
        for attempt in range(3):
            try:
                res = llm.invoke(
                    [
                        SystemMessage(content="Extract the top 5 key learning concepts from this text. Return as a JSON list of strings."),
                        HumanMessage(content=sample),
                    ]
                )
                raw = res.content.strip()
                # tolerate markdown fences
                if "```" in raw:
                    raw = raw.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    validated = ConceptList(concepts=parsed)
                elif isinstance(parsed, dict) and "concepts" in parsed:
                    validated = ConceptList(**parsed)
                else:
                    raise ValueError("unexpected concept payload")
                break
            except Exception as e:
                logger.warning(f"[concepts.extract] LLM parse retry {attempt + 1}/3 for doc {document_id}: {e}")
                if attempt == 2:
                    raise
        else:
            raise RuntimeError("concept extraction retries exhausted")

        inserted = 0
        for name in validated.concepts:
            clean = name.strip()[:200]
            if not clean:
                continue
            exists = (
                db.query(Concept)
                .filter(Concept.project_id == project_id, Concept.name == clean)
                .first()
            )
            if exists:
                continue
            db.add(Concept(project_id=project_id, name=clean, mastery_level=0.0))
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
    db = SessionLocal()
    try:
        pid = uuid.UUID(project_id)
        concept = (
            db.query(Concept)
            .filter(Concept.project_id == pid, Concept.name == concept_name)
            .first()
        )
        if concept is None:
            concept = Concept(project_id=pid, name=concept_name, mastery_level=0.0)
            db.add(concept)
            db.flush()
        score = max(0.0, min(100.0, float(confidence_score)))
        concept.mastery_level = round((float(concept.mastery_level) * 0.7) + (score * 0.3), 2)
        concept.last_assessed_at = datetime.utcnow()
        db.commit()
        logger.success(f"[mastery.chat] project_id={project_id} concept={concept_name} new={concept.mastery_level}")
        return f"updated:{concept.mastery_level}"
    except Exception as e:
        db.rollback()
        logger.error(f"[mastery.chat] failed project {project_id}: {e}")
        return f"failed:{e}"
    finally:
        db.close()
