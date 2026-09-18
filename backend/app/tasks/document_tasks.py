import os
import uuid
from loguru import logger
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.config import settings
from app.db.session import SessionLocal
import app.db.base  # noqa: F401 - register all tables so FKs resolve in the worker
from app.db.models.document import Document, DocumentChunk
from app.tasks.celery_app import celery_app
from app.utils.pdf_parser import parse_pdf


def _fail(db, document, reason: str) -> str:
    """Mark document failed with a UI-visible reason (best-effort, never raises)."""
    short = (reason or "Processing failed")[:500]
    try:
        document.status = "failed"
        if hasattr(document, "error"):
            document.error = short
        db.commit()
        _emit_document_processed(db, document, "failed", reason=short)
    except Exception as e:
        db.rollback()
        logger.warning(f"Could not persist failure for {document.id}: {e}")
    logger.warning(f"Document {document.id} failed: {short}")
    return f"failed:{short}"


def _emit_document_processed(db, document, status: str, reason: str | None = None) -> None:
    """Durable event for a terminal ingest outcome (best-effort, never raises)."""
    from app.services.event_service import emit_event, owner_of_project, DOCUMENT_PROCESSED

    text = f"'{document.file_name}' ({status})"
    if reason and status == "failed":
        text = f"{text}: {reason[:300]}"
    emit_event(
        db,
        type=DOCUMENT_PROCESSED,
        user_id=owner_of_project(db, document.project_id),
        project_id=document.project_id,
        text=text,
        event_key=f"document:{document.id}:{status}",
    )


@celery_app.task(name="documents.process")
def process_document_task(document_id: str) -> str:
    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is None:
            raise ValueError(f"Document {document_id} not found")

        document.status = "processing"
        if hasattr(document, "error"):
            document.error = None
        db.commit()
        logger.info(
            f"Processing document {document_id} file={getattr(document, 'file_path', None)!r} "
            f"exists={os.path.exists(document.file_path) if getattr(document, 'file_path', None) else False}"
        )

        if not settings.GOOGLE_API_KEY:
            return _fail(
                db, document,
                "GOOGLE_API_KEY is not set on the worker. Add it to the worker's Railway env (same value as web) and press Retry.",
            )

        try:
            pages = parse_pdf(document.file_path)
        except RuntimeError as e:
            return _fail(db, document, str(e))
        except Exception as e:
            return _fail(db, document, f"Cannot parse PDF: {e}")

        # Idempotent retry: a previous attempt may have stored chunks before
        # failing — clear them so re-processing never duplicates content.
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
        db.commit()

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001", google_api_key=settings.GOOGLE_API_KEY, output_dimensionality=768)

        chunks: list[DocumentChunk] = []
        for page in pages:
            if not page["text"].strip():
                continue
            for piece in splitter.split_text(page["text"]):
                chunks.append(
                    DocumentChunk(
                        document_id=document.id,
                        project_id=document.project_id,
                        content=piece,
                        page_number=page["page_number"],
                    )
                )

        if not chunks:
            # Honest status: a doc with no extractable text (e.g. an
            # unscannable image-only PDF whose OCR also came back empty)
            # must never reach embeddings or be marked "ready" — the UI
            # would imply it is searchable when nothing was indexed.
            return _fail(
                db, document,
                "No extractable text found. Scanned/image-only PDFs need readable scans (or OCR text layer).",
            )

        try:
            vectors = embeddings.embed_documents([c.content for c in chunks])
        except Exception as e:
            return _fail(db, document, f"Embedding failed (check GOOGLE_API_KEY/quota): {e}")
        for chunk, vector in zip(chunks, vectors):
            chunk.embedding = vector

        db.add_all(chunks)
        document.status = "ready"
        if hasattr(document, "error"):
            document.error = None
        db.commit()
        _emit_document_processed(db, document, "ready")
        logger.success(f"Document {document_id} ready with {len(chunks)} chunks")
        try:
            from app.tasks.concept_tasks import extract_concepts_task

            extract_concepts_task.delay(str(document.id))
        except Exception as ce:
            logger.warning(f"Concept extraction dispatch failed for {document_id}: {ce}")
        return f"ready:{len(chunks)}"
    except Exception as e:
        db.rollback()
        try:
            document = db.get(Document, uuid.UUID(document_id))
            if document is not None:
                return _fail(db, document, str(e))
        except Exception:
            db.rollback()
        logger.error(f"Document {document_id} failed: {e}")
        return f"failed:{e}"
    finally:
        db.close()
