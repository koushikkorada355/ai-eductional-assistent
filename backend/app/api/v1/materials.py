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
    # Write file in chunks to avoid memory overload
    with open(file_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            f.write(chunk)

    document = Document(
        project_id=project.id,
        file_name=file.filename,
        file_path=file_path,
        status="queued",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    process_document_task.delay(str(document.id))

    return document
