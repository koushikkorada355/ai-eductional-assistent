"""Hybrid adaptive mastery routes: DB state + LLM brain, app does the math."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from loguru import logger

from app.db.session import get_db
from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.models.space import Space
from app.db.models.project import Project
from app.db.models.assessment import Concept
from app.db.models.mastery import UserConceptMastery, QuizHistory
from app.schemas.mastery import (
    normalize_concept_name,
    NextQuestionOut,
    SubmitResultOut,
    HistoryOut,
    Recommendation,
)
from app.ai import mastery_engine

router = APIRouter()


class NextRequest(BaseModel):
    project_id: Optional[UUID] = None


class SubmitRequest(BaseModel):
    concept: str = Field(..., min_length=1)
    question_text: str = Field(..., min_length=1)
    question_type: str = Field(..., pattern="^(MCQ|OPEN_ENDED)$")
    user_answer: str = Field(..., min_length=1)
    correct_answer: str = Field(default="")
    project_id: Optional[UUID] = None


def _user_projects(db: Session, user: User) -> list:
    space_ids = [s.id for s in db.query(Space).filter(Space.user_id == user.id).all()]
    if not space_ids:
        return []
    return db.query(Project).filter(Project.space_id.in_(space_ids)).all()


def _resolve_project(db: Session, user: User, project_id: Optional[UUID]) -> Optional[Project]:
    if project_id is not None:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        space = db.query(Space).filter(Space.id == project.space_id).first()
        if not space or space.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this project")
        return project
    projects = _user_projects(db, user)
    return projects[0] if projects else None


def _concepts_for(db: Session, user: User, project: Optional[Project]) -> list:
    if project is not None:
        return db.query(Concept).filter(Concept.project_id == project.id).all()
    projects = _user_projects(db, user)
    if not projects:
        return []
    return db.query(Concept).filter(Concept.project_id.in_([p.id for p in projects])).all()


def _ensure_mastery_rows(db: Session, user: User, concepts: list) -> list:
    existing = {
        m.concept_id: m
        for m in db.query(UserConceptMastery).filter(UserConceptMastery.user_id == user.id).all()
    }
    for c in concepts:
        if c.id not in existing:
            m = UserConceptMastery(user_id=user.id, concept_id=c.id, mastery_score=0)
            db.add(m)
    db.commit()
    return db.query(UserConceptMastery).filter(UserConceptMastery.user_id == user.id).all()


def _mastery_state(db: Session, rows: list) -> list:
    by_id = {c.id: c.name for c in db.query(Concept).all()}
    return [
        {"concept": by_id.get(m.concept_id, "Unknown"), "score": m.mastery_score, "feedback": m.last_feedback or ""}
        for m in rows
    ]


@router.post("/quiz/next", response_model=NextQuestionOut)
def quiz_next(
    body: NextRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _resolve_project(db, current_user, body.project_id)
    concepts = _concepts_for(db, current_user, project)
    if not concepts:
        raise HTTPException(status_code=400, detail="No concepts found. Upload PDFs first.")
    rows = _ensure_mastery_rows(db, current_user, concepts)
    state = _mastery_state(db, [m for m in rows if m.concept_id in {c.id for c in concepts}])

    try:
        decision = mastery_engine.select_next_concept(state)
    except Exception:
        raise HTTPException(status_code=500, detail="Concept selection failed")

    context = ""
    if project is not None:
        try:
            from app.ai.nodes import _rag_context

            context = _rag_context(db, str(project.id), decision.concept)
        except Exception as e:
            logger.warning(f"[quiz.next] grounding failed: {e}")
    try:
        question = mastery_engine.generate_question(decision.concept, decision.question_type, decision.difficulty, context)
    except Exception:
        raise HTTPException(status_code=500, detail="Question generation failed")

    logger.info(f"[quiz.next] user={current_user.id} concept={decision.concept} type={decision.question_type}")
    return {
        "concept": decision.concept,
        "question_type": decision.question_type,
        "difficulty": decision.difficulty,
        "question_text": question.question_text,
        "options": question.options,
        "correct_answer": question.correct_answer,
        "reasoning": decision.reasoning,
    }


@router.post("/quiz/submit", response_model=SubmitResultOut)
def quiz_submit(
    body: SubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        concept_name = normalize_concept_name(body.concept)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    project = _resolve_project(db, current_user, body.project_id)

    concept = (
        db.query(Concept)
        .filter(Concept.project_id == project.id, Concept.name == concept_name)
        .first()
        if project is not None
        else None
    )
    if concept is None:
        if project is None:
            raise HTTPException(status_code=400, detail="No concepts found. Upload PDFs first.")
        concept = Concept(project_id=project.id, name=concept_name, mastery_level=0.0)
        db.add(concept)
        db.flush()

    mastery = (
        db.query(UserConceptMastery)
        .filter(UserConceptMastery.user_id == current_user.id, UserConceptMastery.concept_id == concept.id)
        .first()
    )
    if mastery is None:
        mastery = UserConceptMastery(user_id=current_user.id, concept_id=concept.id, mastery_score=0)
        db.add(mastery)
        db.flush()

    try:
        if body.question_type == "MCQ":
            # Exact Python check per spec (whitespace-tolerant).
            correct = body.user_answer.strip() == (body.correct_answer or "").strip()
            score_delta = 10 if correct else -10
            feedback = "Answered correctly" if correct else "Answered incorrectly"
            is_correct = correct
        else:
            verdict = mastery_engine.evaluate_open_answer(
                body.question_text, body.correct_answer or "", body.user_answer
            )
            score_delta, feedback, is_correct = verdict.score_delta, verdict.feedback, verdict.is_correct
    except Exception:
        raise HTTPException(status_code=500, detail="Answer evaluation failed")

    new_score = max(0, min(100, mastery.mastery_score + score_delta))
    mastery.mastery_score = new_score
    mastery.last_feedback = feedback
    mastery.last_updated = datetime.utcnow()
    db.add(
        QuizHistory(
            user_id=current_user.id,
            concept_id=concept.id,
            question_text=body.question_text,
            question_type=body.question_type,
            user_answer=body.user_answer,
            is_correct=is_correct,
            evaluator_feedback=feedback,
        )
    )
    db.commit()
    logger.info(f"[quiz.submit] user={current_user.id} concept={concept_name} delta={score_delta} new={new_score}")
    return {"is_correct": is_correct, "feedback": feedback, "new_score": new_score}


@router.get("/recommendations", response_model=Recommendation)
def recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(UserConceptMastery).filter(UserConceptMastery.user_id == current_user.id).all()
    state = _mastery_state(db, rows)
    history = (
        db.query(QuizHistory)
        .filter(QuizHistory.user_id == current_user.id)
        .order_by(QuizHistory.created_at.desc())
        .limit(5)
        .all()
    )
    by_id = {c.id: c.name for c in db.query(Concept).all()}
    recent = [
        {
            "concept": by_id.get(h.concept_id, "Unknown"),
            "question": h.question_text,
            "correct": h.is_correct,
            "feedback": h.evaluator_feedback or "",
        }
        for h in history
    ]
    try:
        return mastery_engine.recommend_next(state, recent)
    except Exception:
        raise HTTPException(status_code=500, detail="Recommendation generation failed")


@router.get("/mastery/state")
def my_mastery_state(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(UserConceptMastery).filter(UserConceptMastery.user_id == current_user.id).all()
    return _mastery_state(db, rows)


@router.get("/mastery/history", response_model=List[HistoryOut])
def my_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    history = (
        db.query(QuizHistory)
        .filter(QuizHistory.user_id == current_user.id)
        .order_by(QuizHistory.created_at.desc())
        .limit(20)
        .all()
    )
    by_id = {c.id: c.name for c in db.query(Concept).all()}
    return [
        {
            "id": h.id,
            "concept": by_id.get(h.concept_id),
            "question_text": h.question_text,
            "question_type": h.question_type,
            "user_answer": h.user_answer,
            "is_correct": h.is_correct,
            "evaluator_feedback": h.evaluator_feedback,
            "created_at": h.created_at,
        }
        for h in history
    ]
