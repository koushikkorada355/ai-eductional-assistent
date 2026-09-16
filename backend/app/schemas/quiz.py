from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any


class ConceptOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    mastery_level: float = Field(ge=0.0, le=100.0)
    last_assessed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class QuizOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str = "Untitled Quiz"
    goal: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class QuizQuestionOut(BaseModel):
    id: UUID
    quiz_id: UUID
    concept_id: Optional[UUID] = None
    question_type: str = Field(pattern="^(multiple_choice|open_ended)$")
    question_text: str
    options: Optional[Any] = None
    user_answer: Optional[str] = None
    evaluation: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- LLM structured-output validators ---

class ConceptList(BaseModel):
    concepts: List[str] = Field(..., min_length=1, max_length=5)


class ChatMasterySignal(BaseModel):
    concept_name: str = Field(..., min_length=1)
    confidence_score: float = Field(..., ge=0, le=100)


class OpenEndedEvaluation(BaseModel):
    score: int = Field(..., ge=0, le=100)
    feedback: str
    missing_concepts: List[str] = Field(default_factory=list)


class MCQQuestion(BaseModel):
    question_text: str
    options: List[str] = Field(..., min_length=4, max_length=4)
    correct_answer: str


class QuizAttemptOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str = "Untitled Quiz"
    goal: Optional[str] = None
    status: str
    created_at: datetime
    questions_answered: int = 0
    average_score: Optional[float] = None

    class Config:
        from_attributes = True


class QuizQuestionResultOut(QuizQuestionOut):
    correct_answer: Optional[str] = None


class QuizDetailOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str = "Untitled Quiz"
    goal: Optional[str] = None
    status: str
    created_at: datetime
    questions: List[QuizQuestionResultOut] = Field(default_factory=list)
    average_score: Optional[float] = None

    class Config:
        from_attributes = True

