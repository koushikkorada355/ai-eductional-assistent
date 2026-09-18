"""Flat quiz routes (no space_id in path).

Ownership uses the same pattern as the nested routes: every block validates
that the project/quiz belongs to the authenticated user via dependency
injection (get_owned_project_by_id / get_owned_quiz).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from typing import Optional, Any
from uuid import UUID
from loguru import logger

from app.db.session import get_db
from app.api.deps import get_owned_project_by_id, get_owned_quiz
from app.db.models.project import Project
from app.db.models.assessment import Concept, Quiz, QuizQuestion
from app.schemas.quiz import QuizQuestionOut, QuizDetailOut
from app.utils.pagination import MAX_PAGE_SIZE, PageOut, paginate_query, page_envelope
from app.ai.graphs.quiz_graph import quiz_app
from app.db.checkpointer import robust_ainvoke
from app.ai.nodes import evaluate_answer, update_mastery, MAX_QUESTIONS

router = APIRouter()


class AnswerRequest(BaseModel):
    question_id: UUID
    answer: str = Field(..., min_length=1)


class CreateQuizRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    goal: Optional[str] = Field(default="", max_length=500)
    num_mcq: int = Field(default=3, ge=0, le=10)
    num_open: int = Field(default=2, ge=0, le=10)

    @model_validator(mode="after")
    def _check_total(self):
        total = (self.num_mcq or 0) + (self.num_open or 0)
        if total < 1 or total > 10:
            raise ValueError("Total questions (MCQs + open-ended) must be between 1 and 10")
        return self


class CreateQuizResponse(BaseModel):
    quiz_id: UUID
    name: str
    status: str


class SaveAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=5000)


class SubmitQuizResponse(BaseModel):
    quiz_id: UUID
    status: str


class StartQuizResponse(BaseModel):
    quiz_id: UUID
    question: Optional[QuizQuestionOut] = None
    questions_asked: int = 0
    done: bool = False
    error: Optional[str] = None


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


def _average_score(questions: list) -> Optional[float]:
    scores = [(q.evaluation or {}).get("score") for q in questions if q.user_answer is not None]
    scores = [s for s in scores if isinstance(s, (int, float))]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def _initial_state(project_id: str, quiz_id: str, questions_asked: int) -> dict:
    return {
        "project_id": project_id,
        "quiz_id": quiz_id,
        "messages": [],
        "current_question": "",
        "current_question_id": "",
        "question_type": "",
        "user_answer": "",
        "evaluation": {},
        "concepts_to_test": [],
        "selected_concept": "",
        "selected_concept_id": "",
        "questions_asked": questions_asked,
        "error": "",
    }


@router.post("/projects/{project_id}/quiz/start", response_model=CreateQuizResponse)
async def start_quiz(
    body: CreateQuizRequest,
    project: Project = Depends(get_owned_project_by_id),
    db: Session = Depends(get_db),
):
    has_concepts = db.query(Concept.id).filter(Concept.project_id == project.id).first() is not None
    if not has_concepts:
        raise HTTPException(status_code=400, detail="No concepts found. Upload PDFs first.")
    quiz = Quiz(project_id=project.id, name=body.name.strip(), goal=(body.goal or "").strip(), status="generating")
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    logger.info(f"[quiz.create] project={project.id} quiz={quiz.id} name={quiz.name!r}")

    try:
        from app.tasks.quiz_tasks import generate_batch_task

        generate_batch_task.delay(str(quiz.id), body.num_mcq, body.num_open)
    except Exception as e:
        logger.error(f"[quiz.create] dispatch failed quiz={quiz.id}: {e}")
        quiz.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail="Quiz generation failed to start")
    return {"quiz_id": quiz.id, "name": quiz.name, "status": quiz.status}


@router.patch("/quiz/{quiz_id}/questions/{question_id}/save", response_model=QuizQuestionOut)
def save_answer(
    question_id: UUID,
    body: SaveAnswerRequest,
    quiz: Quiz = Depends(get_owned_quiz),
    db: Session = Depends(get_db),
):
    if quiz.status == "completed":
        raise HTTPException(status_code=400, detail="Quiz already submitted")
    question = db.query(QuizQuestion).filter(QuizQuestion.id == question_id).first()
    if not question or question.quiz_id != quiz.id:
        raise HTTPException(status_code=404, detail="Question not found in this quiz")
    question.user_answer = body.answer.strip()
    db.commit()
    db.refresh(question)
    logger.info(f"[quiz.save] quiz={quiz.id} q={question.id}")
    return _serialize(question)


@router.post("/quiz/{quiz_id}/submit", response_model=SubmitQuizResponse)
def submit_quiz(
    quiz: Quiz = Depends(get_owned_quiz),
    db: Session = Depends(get_db),
):
    if quiz.status == "completed":
        return {"quiz_id": quiz.id, "status": quiz.status}
    quiz.status = "evaluating"
    db.commit()
    logger.info(f"[quiz.submit] quiz={quiz.id}")
    try:
        from app.tasks.quiz_tasks import evaluate_submission_task

        evaluate_submission_task.delay(str(quiz.id))
    except Exception as e:
        logger.error(f"[quiz.submit] dispatch failed quiz={quiz.id}: {e}")
        quiz.status = "in_progress"
        db.commit()
        raise HTTPException(status_code=500, detail="Quiz submission failed to start")
    return {"quiz_id": quiz.id, "status": quiz.status}


@router.post("/projects/{project_id}/quizzes/start-legacy", response_model=StartQuizResponse)
async def start_quiz_legacy(
    project: Project = Depends(get_owned_project_by_id),
    db: Session = Depends(get_db),
):
    quiz = Quiz(project_id=project.id, status="in_progress")
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    logger.info(f"[quiz.start] project={project.id} quiz={quiz.id}")

    config = {"configurable": {"thread_id": str(quiz.id)}}
    try:
        result = await robust_ainvoke(quiz_app, _initial_state(str(project.id), str(quiz.id), 0), config=config)
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


@router.post("/quiz/{quiz_id}/answer", response_model=AnswerResponse)
async def submit_answer(
    body: AnswerRequest,
    quiz: Quiz = Depends(get_owned_quiz),
    db: Session = Depends(get_db),
):
    if quiz.status == "completed":
        raise HTTPException(status_code=400, detail="Quiz already completed")
    question = db.query(QuizQuestion).filter(QuizQuestion.id == body.question_id).first()
    if not question or question.quiz_id != quiz.id:
        raise HTTPException(status_code=404, detail="Question not found in this quiz")
    logger.info(f"[quiz.answer] quiz={quiz.id} q={question.id}")

    eval_state = {
        "project_id": str(quiz.project_id),
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

    config = {"configurable": {"thread_id": str(quiz.id)}}
    try:
        result = await robust_ainvoke(
            quiz_app,
            _initial_state(str(quiz.project_id), str(quiz.id), answered), config=config
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


@router.get("/projects/{project_id}/quizzes", response_model=PageOut)
def list_attempts(
    project: Project = Depends(get_owned_project_by_id),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=10, ge=1, le=MAX_PAGE_SIZE, description="Rows per page"),
):
    rows, total, page, page_size = paginate_query(
        db.query(Quiz)
        .filter(Quiz.project_id == project.id)
        .order_by(Quiz.created_at.desc()),
        page, page_size,
    )
    # Exact stat cards without loading every quiz's questions.
    completed = db.query(Quiz).filter(
        Quiz.project_id == project.id, Quiz.status == "completed").count()
    active = db.query(Quiz).filter(
        Quiz.project_id == project.id,
        Quiz.status.in_(["in_progress", "generating", "evaluating"])).count()
    out = []
    for q in rows:
        questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == q.id).all()
        answered = sum(1 for x in questions if x.user_answer is not None)
        out.append(
            {
                "id": q.id,
                "project_id": q.project_id,
                "name": q.name,
                "goal": q.goal,
                "status": q.status,
                "created_at": q.created_at,
                "questions_answered": answered,
                "average_score": _average_score(questions),
            }
        )
    env = page_envelope(out, total, page, page_size)
    env["summary"] = {"total": total, "completed": completed, "active": active}
    return env


def _serialize_result(q: QuizQuestion, reveal: bool) -> dict:
    data = _serialize(q)
    data["correct_answer"] = q.correct_answer if reveal else None
    if not reveal:
        data["evaluation"] = None
    return data


@router.get("/quiz/{quiz_id}", response_model=QuizDetailOut)
def get_quiz_details(
    quiz: Quiz = Depends(get_owned_quiz),
    db: Session = Depends(get_db),
):
    questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_id == quiz.id)
        .order_by(QuizQuestion.created_at.asc())
        .all()
    )
    reveal = quiz.status == "completed"
    return {
        "id": quiz.id,
        "project_id": quiz.project_id,
        "name": quiz.name,
        "goal": quiz.goal,
        "status": quiz.status,
        "created_at": quiz.created_at,
        "questions": [_serialize_result(q, reveal) for q in questions],
        "average_score": _average_score(questions) if reveal else None,
    }
