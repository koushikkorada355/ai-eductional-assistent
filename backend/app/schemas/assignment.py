from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Dict, Any


class CreateAssignmentRequest(BaseModel):
    concept_ids: List[UUID] = Field(..., min_length=1, max_length=10)
    num_questions: int = Field(default=5, ge=1, le=50)
    title: Optional[str] = Field(default=None, max_length=200)


class SubmitAssignmentRequest(BaseModel):
    # {question_id_str: selected_option_text}
    answers: Dict[str, str] = Field(..., min_length=1)


class AssignmentQuestionOut(BaseModel):
    id: UUID
    question_text: str
    options: List[str]

    class Config:
        from_attributes = True


class AssignmentQuestionResultOut(AssignmentQuestionOut):
    correct_answer: str
    user_answer: str = ""
    is_correct: bool = False


class AssignmentListOut(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    status: str
    num_questions: int = 0
    total: Optional[int] = None
    score: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AssignmentDetailOut(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    status: str
    concept_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    questions: List[Any] = Field(default_factory=list)
    # Present after submission
    answers: Optional[Dict[str, str]] = None
    score: Optional[float] = None
    total: Optional[int] = None
    feedback: Optional[dict] = None
    submitted_at: Optional[datetime] = None


class AssignmentSubmissionOut(BaseModel):
    id: UUID
    assignment_id: UUID
    answers: Optional[Dict[str, str]] = None
    score: float = 0.0
    total: int = 0
    feedback: Optional[dict] = None
    submitted_at: datetime

    class Config:
        from_attributes = True
