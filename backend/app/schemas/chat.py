from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, Any

class MessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)
    citations: Optional[Any] = None

class MessageOut(BaseModel):
    id: UUID
    chat_session_id: UUID
    role: str
    content: str
    citations: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ChatSessionOut(BaseModel):
    id: UUID
    project_id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
