from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description='e.g., "S3 Fundamentals"')
    description: str = Field(..., min_length=1, max_length=500, description="Required description")
    learning_goal: str = Field(..., min_length=1, max_length=500, description="Specific goal for AI Tutor")

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    learning_goal: Optional[str] = Field(None, max_length=500)
    overall_progress: Optional[float] = Field(None, ge=0.0, le=100.0)

class ProjectOut(BaseModel):
    id: UUID
    space_id: UUID
    name: str
    description: Optional[str]
    learning_goal: Optional[str]
    overall_progress: float
    created_at: datetime

    class Config:
        from_attributes = True
