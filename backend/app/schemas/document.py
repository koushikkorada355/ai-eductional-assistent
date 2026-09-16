from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class DocumentOut(BaseModel):
    id: UUID
    project_id: UUID
    file_name: str
    file_path: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
