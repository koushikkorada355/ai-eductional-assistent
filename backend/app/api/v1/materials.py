import hashlib
import os
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_owned_project
from app.db.models.project import Project
from app.db.models.document import Document
from app.schemas.document import DocumentOut
from app.tasks.document_tasks import process_document_task
# from app.services.document_retrieval_service import index_pdf_to_colivara

router = APIRouter()

UPLOAD_DIR = "uploads"


@router.get("/{project_id}/documents", response_model=List[DocumentOut])
def list_documents(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    return db.query(Document).filter(Document.project_id == project.id).order_by(Document.created_at.desc()).all()


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
