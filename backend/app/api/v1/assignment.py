"""Async MCQ Assignment endpoints (Celery + LangGraph, same pattern as quizzes).

Flow:
- POST   /{project_id}/assignments                 -> row (generating) + graph task -> poll ──► ready
- GET    /{project_id}/assignments                 -> list with scores
- GET    /{project_id}/assignments/{assignment_id} -> detail (answers revealed only when submitted)
- POST   /{project_id}/assignments/{assignment_id}/submit -> row (evaluating) + graph task -> poll ──► submitted
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from app.db.session import get_db
from app.api.deps import get_owned_project
from app.db.models.assessment import Assignment, AssignmentQuestion, AssignmentSubmission, Concept
from app.db.models.project import Project
from app.schemas.assignment import (
    AssignmentListOut,
    AssignmentDetailOut,
    CreateAssignmentRequest,
    SubmitAssignmentRequest,
)
from app.services.assignment_service import is_correct
from loguru import logger

router = APIRouter()


def get_assignment(assignment_id: UUID, project_id: UUID, db: Session) -> Assignment:
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id,
        Assignment.project_id == project_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


def _latest_submission(assignment_id: UUID, db: Session) -> AssignmentSubmission | None:
    return db.query(AssignmentSubmission).filter(
        AssignmentSubmission.assignment_id == assignment_id
    ).order_by(AssignmentSubmission.submitted_at.desc()).first()


def _public_questions(assignment: Assignment, db: Session, graded: AssignmentSubmission | None):
    """Questions for detail view. correct_answer only included after grading."""
    questions = db.query(AssignmentQuestion).filter(
        AssignmentQuestion.assignment_id == assignment.id
    ).order_by(AssignmentQuestion.created_at).all()
    answers = (graded.answers or {}) if graded else {}
    out = []
    for q in questions:
        item = {
            "id": str(q.id),
            "question_text": q.question_text,
            "options": q.options or [],
        }
        if graded:
            qid = str(q.id)
            selected = answers.get(qid, "")
            item["correct_answer"] = q.correct_answer
            item["user_answer"] = selected
            item["is_correct"] = is_correct(selected, q.correct_answer)
        out.append(item)
    return out


def _detail_payload(assignment: Assignment, db: Session) -> dict:
    # A submission row exists only after the graph graded (never a pending row).
    submission = _latest_submission(assignment.id, db)
    if submission:
        status = "submitted"
    elif assignment.status == "evaluating":
        status = "evaluating"
    else:
        status = assignment.status
    questions = _public_questions(assignment, db, submission)
    return {
        "id": str(assignment.id),
        "project_id": str(assignment.project_id),
        "title": assignment.title or "Untitled Assignment",
        "status": status,
        "concept_ids": assignment.concept_ids or [],
        "created_at": assignment.created_at,
        "questions": questions,
        "answers": submission.answers if submission else None,
        "score": submission.score if submission else None,
        "total": submission.total if submission else None,
        "feedback": submission.feedback if submission else None,
        "submitted_at": submission.submitted_at if submission else None,
    }


@router.get("/{project_id}/concepts")
async def list_concepts(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """List all concepts for a project."""
    concepts = db.query(Concept).filter(Concept.project_id == project.id).all()
    return [{
        "id": str(c.id),
        "name": c.name,
        "description": c.description,
        "mastery_level": c.mastery_level,
        "document_id": str(c.document_id) if c.document_id else None,
    } for c in concepts]


@router.post("/{project_id}/assignments", response_model=AssignmentDetailOut)
def create_assignment(
    project: Project = Depends(get_owned_project),
    body: CreateAssignmentRequest = None,
    db: Session = Depends(get_db),
):
    """Create an MCQ assignment; questions generate in the background via the graph."""
    if body is None:
        raise HTTPException(status_code=400, detail="Request body is required")
    if not body.concept_ids:
        raise HTTPException(status_code=400, detail="At least one concept must be selected")

    # JSONB cannot store UUID objects -> normalize to strings
    concept_id_strs = [str(cid) for cid in body.concept_ids]
    concepts = db.query(Concept).filter(
        Concept.project_id == project.id,
        Concept.id.in_(concept_id_strs),
    ).all()
    if len(concepts) != len(set(concept_id_strs)):
        raise HTTPException(status_code=400, detail="Some concepts do not belong to this project")

    concept_names = [c.name for c in concepts]
    title = (body.title or "").strip() or f"Assignment: {', '.join(concept_names[:3])}"

    assignment = Assignment(
        project_id=project.id,
        title=title,
        prompt=title,
        concept_ids=concept_id_strs,
        status="generating",
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    logger.info(f"[assignment.create] project={project.id} assignment={assignment.id}")

    try:
        from app.tasks.assignment_tasks import generate_assignment_task

        generate_assignment_task.delay(str(assignment.id), body.num_questions)
    except Exception as e:
        logger.error(f"[assignment.create] dispatch failed assignment={assignment.id}: {e}")
        assignment.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail="Assignment generation failed to start")

    db.refresh(assignment)
    return _detail_payload(assignment, db)


@router.get("/{project_id}/assignments", response_model=list[AssignmentListOut])
def list_assignments(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """List all assignments for a project with scores."""
    assignments = db.query(Assignment).filter(
        Assignment.project_id == project.id
    ).order_by(Assignment.created_at.desc()).all()
    out = []
    for a in assignments:
        num_q = db.query(AssignmentQuestion).filter(
            AssignmentQuestion.assignment_id == a.id
        ).count()
        sub = _latest_submission(a.id, db)
        out.append({
            "id": a.id,
            "project_id": a.project_id,
            "title": a.title or "Untitled Assignment",
            "status": "submitted" if sub else ("evaluating" if a.status == "evaluating" else a.status),
            "num_questions": num_q,
            "total": sub.total if sub else None,
            "score": sub.score if sub else None,
            "created_at": a.created_at,
        })
    return out


@router.get("/{project_id}/assignments/{assignment_id}", response_model=AssignmentDetailOut)
def get_assignment_details(
    assignment_id: UUID,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """Get assignment questions (read-only; answers revealed only after grading)."""
    assignment = get_assignment(assignment_id, project.id, db)
    return _detail_payload(assignment, db)


@router.post("/{project_id}/assignments/{assignment_id}/submit", response_model=AssignmentDetailOut)
def submit_assignment(
    assignment_id: UUID,
    body: SubmitAssignmentRequest,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """Submit MCQ answers; grading runs in the background via the graph."""
    assignment = get_assignment(assignment_id, project.id, db)

    if assignment.status == "generating":
        raise HTTPException(status_code=400, detail="Assignment is still generating, try again shortly")
    if assignment.status == "failed":
        raise HTTPException(status_code=400, detail="Assignment generation failed")

    existing = _latest_submission(assignment.id, db)
    if existing:
        raise HTTPException(status_code=400, detail="Assignment already submitted")
    if assignment.status == "evaluating":
        raise HTTPException(status_code=400, detail="Evaluation already in progress")

    questions = db.query(AssignmentQuestion).filter(
        AssignmentQuestion.assignment_id == assignment.id
    ).order_by(AssignmentQuestion.created_at).all()
    if not questions:
        raise HTTPException(status_code=400, detail="Assignment has no questions")

    valid_ids = {str(q.id) for q in questions}
    answers = {str(k): str(v) for k, v in (body.answers or {}).items()}
    unknown = set(answers) - valid_ids
    if unknown:
        raise HTTPException(status_code=400, detail="Answers contain unknown question IDs")
    invalid = [qid for qid, opt in answers.items()
               if opt not in (next(q.options for q in questions if str(q.id) == qid) or [])]
    if invalid:
        raise HTTPException(status_code=400, detail="One or more answers are not valid options")

    # No submission row yet: the graph creates it when grading commits.
    # Answers travel via the task args; nothing partial persists.
    assignment.status = "evaluating"
    db.commit()
    logger.info(f"[assignment.submit] assignment={assignment.id}")

    try:
        from app.tasks.assignment_tasks import evaluate_assignment_task

        evaluate_assignment_task.delay(str(assignment.id), answers)
    except Exception as e:
        logger.error(f"[assignment.submit] dispatch failed assignment={assignment.id}: {e}")
        assignment.status = "ready"
        db.commit()
        raise HTTPException(status_code=500, detail="Assignment submission failed to start")

    db.refresh(assignment)
    return _detail_payload(assignment, db)
