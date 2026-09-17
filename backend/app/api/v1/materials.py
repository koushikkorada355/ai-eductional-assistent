import hashlib
import os
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_owned_project
from app.db.models.project import Project
from app.db.models.document import Document, DocumentChunk
from app.schemas.document import DocumentOut
from app.tasks.document_tasks import process_document_task
# from app.services.document_retrieval_service import index_pdf_to_colivara

router = APIRouter()

UPLOAD_DIR = "uploads"


def _with_stats(db: Session, doc: Document) -> Document:
    pages, chunks = db.query(func.max(DocumentChunk.page_number), func.count(DocumentChunk.id)).filter(
        DocumentChunk.document_id == doc.id).first()
    doc.pages = pages or 0
    doc.chunks = chunks or 0
    return doc


@router.get("/{project_id}/documents", response_model=List[DocumentOut])
def list_documents(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    docs = db.query(Document).filter(Document.project_id == project.id).order_by(Document.created_at.desc()).all()
    return [_with_stats(db, d) for d in docs]


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
        "document": {"id": doc.id, "file_name": doc.file_name, "status": doc.status},
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
    db.commit()
    db.refresh(doc)
    process_document_task.delay(str(doc.id))
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
    db: Session = Depends(get_db),
):
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    # Write file in chunks to avoid memory overload, hashing as we go
    sha = hashlib.sha256()
    with open(file_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            sha.update(chunk)
            f.write(chunk)
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
        .filter(Document.project_id == project.id, Document.file_name == file.filename)
        .first()
    )
    if same_name:
        try:
            os.remove(file_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=409, detail=f"A file named '{file.filename}' already exists in this project."
        )

    document = Document(
        project_id=project.id,
        file_name=file.filename,
        file_path=file_path,
        file_hash=file_hash,
        status="queued",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # RAG pipeline: parse PDF -> chunk -> Gemini embeddings -> pgvector,
    # executed async via Celery so uploads never block.
    process_document_task.delay(str(document.id))

    # COLIVARA ALTERNATIVE - COMMENTED OUT (revert by swapping these blocks)
    # Visual RAG indexing via ColiVara (one collection per project).
    # index_pdf_to_colivara(file_path, collection_name=str(project.id))

    return document
