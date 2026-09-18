from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class DocumentOut(BaseModel):
    id: UUID
    project_id: UUID
    file_name: str
    # NOTE: file_path is intentionally NOT exposed — it is an absolute
    # server-side path (/data/uploads/... in prod) and must never reach
    # clients. Use file_name + the download/evidence endpoints instead.
    status: str
    created_at: datetime
    # Failure reason when status == "failed" (None otherwise).
    error: Optional[str] = None
    # Additive derived fields (do not affect existing consumers).
    pages: Optional[int] = None
    chunks: Optional[int] = None

    class Config:
        from_attributes = True
