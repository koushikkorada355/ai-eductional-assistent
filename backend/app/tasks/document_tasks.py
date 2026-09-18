import os
import time
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


def _tag(document_id: str, task=None) -> str:
    tid = "n/a"
    try:
        tid = str(getattr(getattr(task, "request", None), "id", "n/a"))[:8]
    except Exception:
        pass
    return f"[JOB documents.process|id={str(document_id)[:8]}|task={tid}]"


def _rss_mb() -> str:
    try:
        import resource

        return f"{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f}MB"
    except Exception:
        return "?"


def _fail(db, document, reason: str, tag: str) -> str:
    """Mark document failed with a UI-visible reason (best-effort, never raises).

    The full raw `reason` stays in the SERVER logs only; clients get the
    sanitized form via public_error (no URLs, paths, keys, or API blobs).
    """
    from app.utils.user_errors import public_error

    logger.warning(f"{tag} raw failure (server-side only): {(reason or '')[:1000]}")
    short = public_error(reason, default="Processing failed")
    try:
        document.status = "failed"
        if hasattr(document, "error"):
            document.error = short
        db.commit()
        _emit_document_processed(db, document, "failed", reason=short)
    except Exception as e:
        db.rollback()
        logger.warning(f"{tag} could not persist failure for {document.id}: {e}")
    logger.warning(f"{tag} FAILED -> status=failed error={short[:200]} rss={_rss_mb()}")
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


@celery_app.task(name="documents.process", bind=True)
def process_document_task(self, document_id: str) -> str:
    t0 = time.monotonic()
    tag = _tag(document_id, self)
    logger.info(f"{tag} received phase=fetch rss={_rss_mb()}")
    db = SessionLocal()
    try:
        try:
            doc_uuid = uuid.UUID(document_id)
        except ValueError:
            logger.error(f"{tag} phase=fetch invalid uuid")
            return "failed:invalid-id"

        document = db.get(Document, doc_uuid)
        if document is None:
            logger.error(f"{tag} phase=fetch not found in DB (deleted? wrong DATABASE_URL on worker?)")
            return "failed:not-found"

        file_path = getattr(document, "file_path", None)
        try:
            fsize = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else -1
        except OSError:
            fsize = -1
        logger.info(
            f"{tag} phase=fetch status={document.status} file={file_path!r} "
            f"exists={bool(file_path and os.path.exists(file_path))} size={fsize}B "
            f"upload_dir={os.path.abspath((settings.UPLOAD_DIR or os.getenv('UPLOAD_DIR', 'uploads')).strip() or 'uploads')}"
        )

        document.status = "processing"
        if hasattr(document, "error"):
            document.error = None
        db.commit()
        logger.info(f"{tag} phase=parse start (PyMuPDF + OCR fallback)")

        if not settings.GOOGLE_API_KEY:
            logger.error(f"{tag} phase=precheck GOOGLE_API_KEY=<absent> on worker")
            return _fail(
                db, document,
                "GOOGLE_API_KEY is not set on the worker. Add it to the worker's Railway env (same value as web) and press Retry.",
                tag,
            )
        logger.info(f"{tag} phase=precheck GOOGLE_API_KEY=set({len((settings.GOOGLE_API_KEY or '').strip())} chars)")

        t_parse = time.monotonic()
        try:
            pages = parse_pdf(document.file_path)
        except RuntimeError as e:
            logger.error(f"{tag} phase=parse failed: {e}")
            return _fail(db, document, str(e), tag)
        except Exception as e:
            logger.opt(exception=True).error(f"{tag} phase=parse crashed: {type(e).__name__}: {e}")
            return _fail(db, document, f"Cannot parse PDF: {e}", tag)
        ocr_pages = sum(1 for p in pages if p.get("source") == "ocr")
        empty_pages = sum(1 for p in pages if p.get("source") == "empty")
        total_chars = sum(len(p.get("text") or "") for p in pages)
        logger.info(
            f"{tag} phase=parse done in {time.monotonic() - t_parse:.1f}s "
            f"pages={len(pages)} ocr={ocr_pages} empty={empty_pages} chars={total_chars} rss={_rss_mb()}"
        )

        # Crash guards for small workers: one giant doc must fail honestly
        # with "split it" instead of OOM-killing the worker mid-embedding.
        MAX_PDF_PAGES = 300
        MAX_CHUNKS = 2000
        EMBED_BATCH_SIZE = 32
        if len(pages) > MAX_PDF_PAGES:
            logger.warning(f"{tag} phase=guard pages={len(pages)} > max={MAX_PDF_PAGES}")
            return _fail(
                db, document,
                f"PDF has {len(pages)} pages (max {MAX_PDF_PAGES} per upload). "
                "Split it into smaller PDFs and upload each part.",
                tag,
            )

        # Idempotent retry: a previous attempt may have stored chunks before
        # failing — clear them so re-processing never duplicates content.
        cleared = db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
        db.commit()
        if cleared:
            logger.info(f"{tag} phase=cleanup cleared {cleared} stale chunks from previous attempt")

        t_split = time.monotonic()
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
        logger.info(f"{tag} phase=split done in {time.monotonic() - t_split:.1f}s chunks={len(chunks)} rss={_rss_mb()}")

        if not chunks:
            # Honest status: a doc with no extractable text (e.g. an
            # unscannable image-only PDF whose OCR also came back empty)
            # must never reach embeddings or be marked "ready" — the UI
            # would imply it is searchable when nothing was indexed.
            return _fail(
                db, document,
                "No extractable text found. Scanned/image-only PDFs need readable scans (or OCR text layer).",
                tag,
            )

        if len(chunks) > MAX_CHUNKS:
            logger.warning(f"{tag} phase=guard chunks={len(chunks)} > max={MAX_CHUNKS}")
            return _fail(
                db, document,
                f"PDF produced {len(chunks)} chunks (max {MAX_CHUNKS}). "
                "Split it into smaller PDFs and upload each part.",
                tag,
            )

        # Embed in small batches: one giant call balloons request memory and
        # a single API timeout would fail the whole doc with nothing stored.
        t_embed = time.monotonic()
        try:
            total = len(chunks)
            for start in range(0, total, EMBED_BATCH_SIZE):
                batch = chunks[start:start + EMBED_BATCH_SIZE]
                try:
                    vectors = embeddings.embed_documents([c.content for c in batch])
                except Exception as e:
                    logger.opt(exception=True).error(
                        f"{tag} phase=embed batch {start + 1}-{start + len(batch)}/{total} failed: "
                        f"{type(e).__name__}: {e}"
                    )
                    return _fail(
                        db, document,
                        f"Embedding failed on chunks {start + 1}-{start + len(batch)} of {total} "
                        f"(check GOOGLE_API_KEY/quota): {e}",
                        tag,
                    )
                for chunk, vector in zip(batch, vectors):
                    chunk.embedding = vector
                logger.info(
                    f"{tag} phase=embed {min(start + len(batch), total)}/{total} "
                    f"elapsed={time.monotonic() - t_embed:.1f}s rss={_rss_mb()}"
                )
        except Exception as e:
            logger.opt(exception=True).error(f"{tag} phase=embed crashed: {e}")
            return _fail(db, document, f"Embedding failed (check GOOGLE_API_KEY/quota): {e}", tag)

        t_save = time.monotonic()
        db.add_all(chunks)
        document.status = "ready"
        if hasattr(document, "error"):
            document.error = None
        db.commit()
        _emit_document_processed(db, document, "ready")
        logger.success(
            f"{tag} DONE phase=save chunks={len(chunks)} save={time.monotonic() - t_save:.1f}s "
            f"total={time.monotonic() - t0:.1f}s rss={_rss_mb()}"
        )
        try:
            from app.tasks.concept_tasks import extract_concepts_task

            nxt = extract_concepts_task.apply_async(args=[str(document.id)], ignore_result=True)
            logger.info(f"{tag} phase=chain dispatched concepts.extract task={getattr(nxt, 'id', '?')}")
        except Exception as ce:
            logger.warning(f"{tag} phase=chain concepts.extract dispatch failed: {ce}")
        return f"ready:{len(chunks)}"
    except Exception as e:
        db.rollback()
        logger.opt(exception=True).error(f"{tag} UNHANDLED after {time.monotonic() - t0:.1f}s: {type(e).__name__}: {e}")
        try:
            document = db.get(Document, uuid.UUID(document_id))
            if document is not None:
                return _fail(db, document, f"{type(e).__name__}: {e}", tag)
        except Exception:
            db.rollback()
        return f"failed:{e}"
    finally:
        db.close()
