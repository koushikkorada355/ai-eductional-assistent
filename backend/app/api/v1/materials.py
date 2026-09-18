import hashlib
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.config import settings
from app.db.session import get_db
from app.api.deps import get_current_user, get_owned_project
from app.db.models.project import Project
from app.db.models.user import User
from app.db.models.document import Document, DocumentChunk
from app.schemas.document import DocumentOut
from app.services.event_service import emit_event, MATERIAL_UPLOADED
from app.tasks.document_tasks import process_document_task
from app.utils.pagination import MAX_PAGE_SIZE, PageOut, paginate_query, page_envelope
# from app.services.document_retrieval_service import index_pdf_to_colivara

router = APIRouter()


def _get_upload_dir() -> str:
    """Absolute upload dir shared by web + worker.

    Local dev: ./uploads (resolved absolute). Production (Railway): set
    UPLOAD_DIR=/data/uploads on BOTH web and worker and mount the SAME
    volume at /data/uploads, otherwise the worker can't see the file.
    """
    raw = (getattr(settings, "UPLOAD_DIR", None) or os.getenv("UPLOAD_DIR", "uploads")).strip() or "uploads"
    path = os.path.abspath(raw)
    os.makedirs(path, exist_ok=True)
    return path


def _max_upload_bytes() -> int:
    try:
        mb = int(getattr(settings, "MAX_UPLOAD_MB", 25) or 25)
    except (TypeError, ValueError):
        mb = 25
    return max(1, mb) * 1024 * 1024


def _live_redis_url() -> str | None:
    """Live URL: env wins so a just-changed Railway value is used immediately."""
    import os

    for candidate in (os.getenv("REDIS_URL"), getattr(settings, "REDIS_URL", None)):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _redis_label(url: str | None = None) -> str:
    """Redacted Redis host for error messages (no password leak)."""
    try:
        from urllib.parse import urlsplit

        if url is None:
            url = _live_redis_url() or ""
        url = (url or "").strip()
        if not url:
            return "<REDIS_URL unset>"
        parts = urlsplit(url)
        host = parts.hostname or "?"
        port = f":{parts.port}" if parts.port else ""
        return f"{parts.scheme or '?'}://{host}{port}"
    except Exception:
        return "<unparseable REDIS_URL>"


def _friendly_queue_error(e: Exception) -> str:
    raw = str(e).strip() or type(e).__name__
    redis = _redis_label()
    low = raw.lower()
    if "redis_url" in low and "not set" in low or redis == "<REDIS_URL unset>":
        return (
            "REDIS_URL is not set on the web service. Set it (same value as worker) and restart web, then Retry."
        )
    if "result store backend" in low or "must be restarted" in low:
        return (
            f"Cannot reach Redis result store at {redis} ({raw[:160]}). "
            "Check: 1) Railway Redis service is Running, 2) web + worker share the SAME internal REDIS_URL "
            "(not redis://redis:6379/0 in prod), 3) restart WEB after changing env (Celery caches it), then Retry."
        )
    if "name or service not known" in low or "temporary failure in name resolution" in low or "nodename nor servname" in low:
        return (
            f"Redis host does not resolve ({redis}): {raw[:160]}. "
            "On Railway use the Redis service internal URL on BOTH web and worker (local 'redis' hostname only works in docker-compose), then restart web and Retry."
        )
    if "auth" in low or "password" in low or "noauth" in low:
        return (
            f"Redis auth failed at {redis}: {raw[:160]}. Copy the full internal REDIS_URL (with password) from the Redis service into BOTH web and worker, restart web, then Retry."
        )
    if "refused" in low or "timed out" in low or "timeout" in low:
        return (
            f"Redis unreachable at {redis}: {raw[:160]}. Check the Redis service is Running (not sleeping/crashed), then restart web and Retry."
        )
    return f"Queue error at {redis}: {raw[:200]}. Check Redis is Running, web+worker share the same REDIS_URL, restart web, then Retry."


def _dispatch_process_document(document_id: str) -> str | None:
    """Enqueue background processing. Returns None on success, friendly error str on failure."""
    # Refresh Celery's cached broker so a just-changed REDIS_URL works
    # without a full web restart clearing Kombu's stale connection.
    try:
        from app.tasks.celery_app import refresh_broker_from_env

        refresh_broker_from_env()
    except Exception as e:
        logger.warning(f"Broker refresh skipped: {e}")
    redis_url = _live_redis_url()
    if not redis_url:
        msg = "REDIS_URL is not set on the web service"
        logger.warning(f"Celery dispatch skipped for document {document_id}: {msg}")
        return msg
    # Fast pre-check so a wrong host gives an actionable error in ~3s
    # instead of Kombu's long reconnect loop ("Retry limit exceeded...").
    try:
        import redis as redis_lib

        client = redis_lib.from_url(redis_url, socket_timeout=3, socket_connect_timeout=3)
        client.ping()
    except Exception as e:
        friendly = _friendly_queue_error(e)
        logger.warning(f"Redis ping failed before dispatch of {document_id}: {friendly}")
        return friendly
    try:
        # ignore_result=True: status lives in Postgres, so dispatch must not
        # touch the result backend (avoids 'result store backend' failures).
        process_document_task.apply_async(args=[str(document_id)], ignore_result=True)
        return None
    except Exception as e:
        friendly = _friendly_queue_error(e)
        logger.warning(f"Celery dispatch failed for document {document_id}: {friendly}")
        return friendly


def _process_inline(document_id: str) -> str:
    """Run the RAG pipeline synchronously in the web process.

    Used as a fallback when Redis/worker is unreachable, and avoids the
    shared-volume problem entirely (web just wrote the file locally).
    Returns the task's result string (ready:... / failed:...).
    """
    try:
        return process_document_task.run(str(document_id))
    except Exception as e:
        logger.warning(f"Inline processing failed for {document_id}: {e}")
        return f"failed:{e}"


def _workers_alive(timeout: float = 1.5) -> bool | None:
    """True if ≥1 worker replied, False if broker ok but none replied, None if unknown.

    Short timeout so Retry stays snappy. Never raises.
    """
    try:
        from app.tasks.celery_app import refresh_broker_from_env, celery_app

        try:
            refresh_broker_from_env()
        except Exception:
            pass
        ping = celery_app.control.ping(timeout=timeout)
        if ping:
            return True
        return False
    except Exception as e:
        logger.warning(f"Worker ping skipped: {e}")
        return None


def _dispatch_or_process_inline(db: Session, doc: Document, check_workers: bool = False) -> None:
    """Prefer async Celery; fall back to inline so docs never stay queued forever.

    On async success: doc stays queued and worker will mark ready/failed —
    unless check_workers=True (Retry path) and no worker replies, in which
    case inline runs immediately instead of stranding the doc.
    On async failure: run inline on web (file is local here). The task itself
    sets doc.status/error, so just refresh the row afterwards.
    """
    dispatch_err = _dispatch_process_document(str(doc.id))
    if not dispatch_err:
        if not check_workers:
            return
        alive = _workers_alive()
        if alive is not False:
            # Worker alive (True) or unknown (None, e.g. ping error) — leave
            # queued; worker or a later Retry will finish it.
            return
        dispatch_err = (
            "Redis is reachable but no workers replied (worker service not running, "
            "scaled to 0, crashed, or on a different REDIS_URL). Running inline instead."
        )
        logger.warning(f"No workers for {doc.id}, trying inline: {dispatch_err}")
    else:
        logger.warning(f"Async dispatch failed for {doc.id}, trying inline: {dispatch_err}")
    try:
        result = _process_inline(str(doc.id))
    except Exception as e:
        result = f"failed:{e}"
    try:
        db.expire_all()
        refreshed = db.query(Document).filter(Document.id == doc.id).first()
        if refreshed is not None:
            doc.status = refreshed.status
            if hasattr(doc, "error"):
                doc.error = getattr(refreshed, "error", None)
            doc.file_name = refreshed.file_name
            doc.file_path = refreshed.file_path
    except Exception as e:
        logger.warning(f"Could not refresh {doc.id} after inline run: {e}")
    # If inline also left it queued/failed-with-queue-error, explain both.
    current_err = getattr(doc, "error", None)
    if getattr(doc, "status", None) == "queued" or (
        getattr(doc, "status", None) == "failed" and current_err and "worker is unreachable" in current_err
    ):
        if hasattr(doc, "error"):
            doc.error = (
                "Upload saved but background worker is unreachable "
                f"(queue error: {dispatch_err}; inline result: {result[:200]}). "
                "Check: worker service Running (not stopped/scaled-to-0/crashed), same REDIS_URL "
                "on web+worker, restart web, then Retry. Details: GET /health/queue."
            )
            try:
                db.commit()
                db.refresh(doc)
            except Exception:
                db.rollback()
    else:
        # Inline completed (ready or honest failed like no-text/API key) —
        # task already set a specific error; just persist the refreshed state.
        try:
            db.commit()
            db.refresh(doc)
        except Exception:
            db.rollback()
    logger.info(f"Inline fallback for {doc.id}: {result[:200]} -> status={getattr(doc, 'status', '?')}")


def _with_stats(db: Session, doc: Document) -> Document:
    pages, chunks = db.query(func.max(DocumentChunk.page_number), func.count(DocumentChunk.id)).filter(
        DocumentChunk.document_id == doc.id).first()
    doc.pages = pages or 0
    doc.chunks = chunks or 0
    return doc


@router.get("/{project_id}/documents", response_model=PageOut)
def list_documents(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE, description="Rows per page"),
):
    rows, total, page, page_size = paginate_query(
        db.query(Document).filter(Document.project_id == project.id).order_by(Document.created_at.desc()),
        page, page_size,
    )
    return page_envelope(
        [DocumentOut.model_validate(_with_stats(db, d)) for d in rows], total, page, page_size
    )


@router.get("/{project_id}/documents/{document_id}/evidence")
def document_evidence(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id, Document.project_id == project.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc.id)
        .order_by(DocumentChunk.page_number)
        .limit(20)
        .all()
    )
    return {
        "document": {
            "id": doc.id,
            "file_name": doc.file_name,
            "status": doc.status,
            "error": getattr(doc, "error", None),
        },
        "evidence": [{"page_number": c.page_number, "excerpt": (c.content or "")[:600]} for c in chunks],
    }


@router.post("/{project_id}/documents/{document_id}/retry", response_model=DocumentOut)
def retry_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id, Document.project_id == project.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.status = "queued"
    if hasattr(doc, "error"):
        doc.error = None
    db.commit()
    db.refresh(doc)
    # Retry is user-initiated: also go inline when no worker is listening,
    # so a stopped worker service can't strand docs in queued silently.
    _dispatch_or_process_inline(db, doc, check_workers=True)
    return _with_stats(db, doc)


@router.delete("/{project_id}/documents/{document_id}", status_code=204)
def delete_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id, Document.project_id == project.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
    try:
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except OSError:
        pass
    db.delete(doc)
    db.commit()
    return None


@router.post("/{project_id}/upload-pdf", response_model=DocumentOut)
async def upload_pdf(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    project: Project = Depends(get_owned_project),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    original_name = (file.filename or "").strip()
    if file.content_type != "application/pdf" and not original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    # Sanitize: strip any client path, fall back to a safe default.
    safe_display_name = os.path.basename(original_name) or "upload.pdf"
    if not safe_display_name.lower().endswith(".pdf"):
        safe_display_name += ".pdf"

    try:
        upload_dir = _get_upload_dir()
    except OSError as e:
        logger.error(f"Upload dir unavailable: {e}")
        raise HTTPException(status_code=500, detail=f"Upload storage unavailable: {e}")

    max_bytes = _max_upload_bytes()
    safe_name = f"{uuid.uuid4()}_{safe_display_name}"
    file_path = os.path.abspath(os.path.join(upload_dir, safe_name))
    # Write file in chunks to avoid memory overload, hashing + size-limit as we go
    sha = hashlib.sha256()
    total = 0
    first_bytes = b""
    try:
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                if not first_bytes:
                    first_bytes = chunk[:8]
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"PDF too large ({total // (1024 * 1024)}MB). Max is {max_bytes // (1024 * 1024)}MB.",
                    )
                sha.update(chunk)
                f.write(chunk)
    except HTTPException:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass
        raise
    except OSError as e:
        logger.error(f"Failed writing upload {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not save upload: {e}")

    if total == 0:
        try:
            os.remove(file_path)
        except OSError:
            pass
        raise HTTPException(status_code=400, detail="Uploaded file is empty. Please choose a valid PDF.")

    # Reject non-PDF content early (e.g. renamed .exe/.html) with a clear 400.
    try:
        with open(file_path, "rb") as f:
            header = f.read(2048).lstrip(b"\xef\xbb\xbf \t\r\n")
            if not header.startswith(b"%PDF"):
                os.remove(file_path)
                raise HTTPException(
                    status_code=400,
                    detail="File is not a valid PDF (missing %PDF header). Please re-export and upload again.",
                )
    except HTTPException:
        raise
    except OSError as e:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=f"Could not verify upload: {e}")

    file_hash = sha.hexdigest()

    # No duplicate content in the same project
    dupe = (
        db.query(Document)
        .filter(Document.project_id == project.id, Document.file_hash == file_hash)
        .first()
    )
    if dupe:
        try:
            os.remove(file_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=409, detail=f"This file was already uploaded as '{dupe.file_name}'."
        )

    # No duplicate file names in the same project
    same_name = (
        db.query(Document)
        .filter(Document.project_id == project.id, Document.file_name == safe_display_name)
        .first()
    )
    if same_name:
        try:
            os.remove(file_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=409, detail=f"A file named '{safe_display_name}' already exists in this project."
        )

    kwargs = dict(
        project_id=project.id,
        file_name=safe_display_name,
        file_path=file_path,
        file_hash=file_hash,
        status="queued",
    )
    if hasattr(Document, "error"):
        kwargs["error"] = None
    document = Document(**kwargs)
    db.add(document)
    db.commit()
    db.refresh(document)
    emit_event(db, type=MATERIAL_UPLOADED, user_id=current_user.id, project_id=project.id,
               text=f"Uploaded '{document.file_name}'",
               event_key=f"document:{document.id}:uploaded")

    # RAG pipeline: parse PDF -> chunk -> Gemini embeddings -> pgvector.
    # Prefer async Celery; fall back to inline on web so a dead Redis/worker
    # can never strand docs in 'queued' (web just wrote the file locally,
    # so inline also dodges the shared-volume problem).
    _dispatch_or_process_inline(db, document)

    # COLIVARA ALTERNATIVE - COMMENTED OUT (revert by swapping these blocks)
    # Visual RAG indexing via ColiVara (one collection per project).
    # index_pdf_to_colivara(file_path, collection_name=str(project.id))

    return _with_stats(db, document)
