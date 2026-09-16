import re
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, List

# STRICT RULE: concepts are short topic names / noun phrases
# ("Newton's Second Law"), NEVER sentences or questions.
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\s'\-().&/]*$")


def normalize_concept_name(v: str) -> str:
    v = (v or "").strip().strip('"').strip()
    if not v:
        raise ValueError("Concept name must be a short topic name, not empty")
    if v.endswith("?"):
        raise ValueError("Concept must be a topic name, never a question")
    if len(v.split()) > 8:
        raise ValueError("Concept must be a short topic name (max 8 words)")
    if not _NAME_RE.match(v):
        raise ValueError("Concept must be a plain topic noun phrase")
    return v


class ConceptOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class MasteryOut(BaseModel):
    concept: str
    score: int = Field(ge=0, le=100)
    feedback: Optional[str] = None

    class Config:
        from_attributes = True


class SelectorDecision(BaseModel):
    concept: str
    question_type: str = Field(pattern="^(MCQ|OPEN_ENDED)$")
    difficulty: str = Field(pattern="^(Easy|Medium|Hard)$")
    reasoning: str

    @field_validator("concept")
    @classmethod
    def _short_name(cls, v: str) -> str:
        return normalize_concept_name(v)


class GeneratedQuestion(BaseModel):
    question_text: str
    options: List[str] = Field(default_factory=list)
    correct_answer: str


class EvaluatorVerdict(BaseModel):
    is_correct: bool
    score_delta: int = Field(ge=-15, le=15)
    feedback: str


class Recommendation(BaseModel):
    growth_summary: str
    recommendation_text: str


class NextQuestionOut(BaseModel):
    concept: str
    question_type: str
    difficulty: str
    question_text: str
    options: List[str] = Field(default_factory=list)
    correct_answer: str
    reasoning: Optional[str] = None


class SubmitResultOut(BaseModel):
    is_correct: bool
    feedback: str
    new_score: int = Field(ge=0, le=100)


class HistoryOut(BaseModel):
    id: UUID
    concept: Optional[str] = None
    question_text: str
    question_type: str
    user_answer: str
    is_correct: bool
    evaluator_feedback: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
