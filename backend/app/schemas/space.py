from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

class SpaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description='e.g., "AWS Certification"')
    description: Optional[str] = Field(None, max_length=500)

class SpaceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class SpaceOut(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
