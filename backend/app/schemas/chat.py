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
    suggested_questions: Optional[list] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ChatSessionOut(BaseModel):
    id: UUID
    project_id: UUID
    title: str = "New conversation"
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)


class ConversationUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class ConversationOut(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    last_preview: Optional[str] = None

    class Config:
        from_attributes = True
