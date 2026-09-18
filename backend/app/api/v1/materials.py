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


def _dispatch_process_document(document_id: str) -> str | None:
    """Enqueue background processing. Returns None on success, error str on failure."""
    try:
        process_document_task.delay(str(document_id))
        return None
    except Exception as e:
        logger.warning(f"Celery dispatch failed for document {document_id}: {e}")
        return str(e)


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
    dispatch_err = _dispatch_process_document(str(doc.id))
    if dispatch_err:
        # Queue unreachable: keep doc queued so a later retry can succeed,
        # but record why so the UI can explain instead of failing silently.
        if hasattr(doc, "error"):
            doc.error = (
                "Upload saved but background worker is unreachable "
                f"(queue error: {dispatch_err}). The file is kept — press Retry once the worker/Redis is up."
            )
            db.commit()
            db.refresh(doc)
        logger.warning(f"Retry queued without worker dispatch for {doc.id}: {dispatch_err}")
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

    # RAG pipeline: parse PDF -> chunk -> Gemini embeddings -> pgvector,
    # executed async via Celery so uploads never block.
    dispatch_err = _dispatch_process_document(str(document.id))
    if dispatch_err and hasattr(document, "error"):
        # Don't fail the upload when Redis/worker is down: the file is safely
        # stored and Retry can dispatch later. Record why for the UI.
        document.error = (
            "Upload saved but background worker is unreachable "
            f"(queue error: {dispatch_err}). Press Retry once the worker/Redis is up."
        )
        db.commit()
        db.refresh(document)
        logger.warning(f"Upload {document.id} saved without dispatch: {dispatch_err}")

    # COLIVARA ALTERNATIVE - COMMENTED OUT (revert by swapping these blocks)
    # Visual RAG indexing via ColiVara (one collection per project).
    # index_pdf_to_colivara(file_path, collection_name=str(project.id))

    return _with_stats(db, document)
