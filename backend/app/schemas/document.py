from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class DocumentOut(BaseModel):
    id: UUID
    project_id: UUID
    file_name: str
    file_path: str
    status: str
    created_at: datetime
    # Failure reason when status == "failed" (None otherwise).
    error: Optional[str] = None
    # Additive derived fields (do not affect existing consumers).
    pages: Optional[int] = None
    chunks: Optional[int] = None

    class Config:
        from_attributes = True
