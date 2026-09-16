from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from uuid import UUID
from loguru import logger

from app.db.session import get_db
from app.api.deps import get_owned_project
from app.db.models.project import Project
from app.db.models.assessment import Concept, Quiz, QuizQuestion
from app.schemas.quiz import ConceptOut, QuizQuestionOut
from app.ai.graphs.quiz_graph import quiz_app
from app.ai.nodes import evaluate_answer, update_mastery, MAX_QUESTIONS

router = APIRouter()


class StartQuizResponse(BaseModel):
    quiz_id: UUID
    question: Optional[QuizQuestionOut] = None
    questions_asked: int = 0
    done: bool = False
    error: Optional[str] = None


class AnswerRequest(BaseModel):
    question_id: UUID
    answer: str = Field(..., min_length=1)


class AnswerResponse(BaseModel):
    evaluation: Optional[Any] = None
    next_question: Optional[QuizQuestionOut] = None
    questions_answered: int = 0
    done: bool = False


def _serialize(q: QuizQuestion) -> dict:
    return {
        "id": q.id,
        "quiz_id": q.quiz_id,
        "concept_id": q.concept_id,
        "question_type": q.question_type,
        "question_text": q.question_text,
        "options": q.options,
        "user_answer": q.user_answer,
        "evaluation": q.evaluation,
        "created_at": q.created_at,
    }


def _get_owned_quiz(quiz_id: UUID, project: Project, db: Session) -> Quiz:
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz or quiz.project_id != project.id:
        raise HTTPException(status_code=404, detail="Quiz not found in this project")
    return quiz


@router.post("/{project_id}/quizzes/start", response_model=StartQuizResponse)
async def start_quiz(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    quiz = Quiz(project_id=project.id, status="in_progress")
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    logger.info(f"[quiz.start] project={project.id} quiz={quiz.id}")

    config = {"configurable": {"thread_id": str(quiz.id)}}
    try:
        result = await quiz_app.ainvoke(
            {
                "project_id": str(project.id),
                "quiz_id": str(quiz.id),
                "messages": [],
                "current_question": "",
                "current_question_id": "",
                "question_type": "",
                "user_answer": "",
                "evaluation": {},
                "concepts_to_test": [],
                "selected_concept": "",
                "selected_concept_id": "",
                "questions_asked": 0,
                "error": "",
            },
            config=config,
        )
    except Exception as e:
        logger.error(f"[quiz.start] graph failed quiz={quiz.id}: {e}")
        raise HTTPException(status_code=500, detail="Quiz generation failed")

    if result.get("error"):
        quiz.status = "failed"
        db.commit()
        return {"quiz_id": quiz.id, "question": None, "questions_asked": 0, "done": True, "error": result["error"]}

    db.expire_all()
    qq = db.query(QuizQuestion).filter(QuizQuestion.id == result["current_question_id"]).first()
    if not qq:
        raise HTTPException(status_code=500, detail="Question persistence failed")
    return {"quiz_id": quiz.id, "question": _serialize(qq), "questions_asked": result.get("questions_asked", 1), "done": False}


@router.post("/{project_id}/quizzes/{quiz_id}/answer", response_model=AnswerResponse)
async def submit_answer(
    quiz_id: UUID,
    body: AnswerRequest,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    quiz = _get_owned_quiz(quiz_id, project, db)
    if quiz.status == "completed":
        raise HTTPException(status_code=400, detail="Quiz already completed")
    question = db.query(QuizQuestion).filter(QuizQuestion.id == body.question_id).first()
    if not question or question.quiz_id != quiz.id:
        raise HTTPException(status_code=404, detail="Question not found in this quiz")
    logger.info(f"[quiz.answer] quiz={quiz.id} q={question.id}")

    # 1. Evaluate + mastery via graph nodes (sync DB writes; open-ended chains celery)
    eval_state = {
        "project_id": str(project.id),
        "quiz_id": str(quiz.id),
        "current_question_id": str(question.id),
        "question_type": question.question_type,
        "user_answer": body.answer,
        "selected_concept": "",
        "evaluation": {},
    }
    evaluate_answer(eval_state)
    try:
        update_mastery({**eval_state, "question_type": question.question_type})
    except Exception as e:
        logger.warning(f"[quiz.answer] mastery step failed: {e}")
    db.expire_all()

    question = db.query(QuizQuestion).filter(QuizQuestion.id == body.question_id).first()
    evaluation = question.evaluation if question else None

    answered = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz.id, QuizQuestion.user_answer.isnot(None)).count()
    if answered >= MAX_QUESTIONS:
        quiz.status = "completed"
        db.commit()
        logger.info(f"[quiz.answer] quiz={quiz.id} completed")
        return {"evaluation": evaluation, "next_question": None, "questions_answered": answered, "done": True}

    # 2. Next question via graph (same thread_id so checkpointer persists)
    config = {"configurable": {"thread_id": str(quiz.id)}}
    try:
        result = await quiz_app.ainvoke(
            {
                "project_id": str(project.id),
                "quiz_id": str(quiz.id),
                "messages": [],
                "current_question": "",
                "current_question_id": "",
                "question_type": "",
                "user_answer": "",
                "evaluation": {},
                "concepts_to_test": [],
                "selected_concept": "",
                "selected_concept_id": "",
                "questions_asked": answered,
                "error": "",
            },
            config=config,
        )
    except Exception as e:
        logger.error(f"[quiz.answer] next-question failed quiz={quiz.id}: {e}")
        return {"evaluation": evaluation, "next_question": None, "questions_answered": answered, "done": False}

    db.expire_all()
    nxt = None
    if result.get("current_question_id"):
        nq = db.query(QuizQuestion).filter(QuizQuestion.id == result["current_question_id"]).first()
        nxt = _serialize(nq) if nq else None
    return {"evaluation": evaluation, "next_question": nxt, "questions_answered": answered, "done": False}


@router.get("/{project_id}/mastery", response_model=List[ConceptOut])
def get_mastery(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    return (
        db.query(Concept)
        .filter(Concept.project_id == project.id)
        .order_by(Concept.mastery_level.asc())
        .all()
    )
