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


@celery_app.task(name="documents.process")
def process_document_task(document_id: str) -> str:
    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is None:
            raise ValueError(f"Document {document_id} not found")

        document.status = "processing"
        db.commit()

        if not settings.GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY is not set")

        pages = parse_pdf(document.file_path)

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

        vectors = embeddings.embed_documents([c.content for c in chunks])
        for chunk, vector in zip(chunks, vectors):
            chunk.embedding = vector

        db.add_all(chunks)
        document.status = "ready"
        db.commit()
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
                document.status = "failed"
                db.commit()
        except Exception:
            db.rollback()
        logger.error(f"Document {document_id} failed: {e}")
        return f"failed:{e}"
    finally:
        db.close()
