"""Assignment graph nodes (sync, worker-safe: each opens its own DB session).

Called by Celery tasks via the compiled assignment graph; the API never calls
these directly. Pure LLM helpers stay in app/services/assignment_service.py.
"""
import uuid
from loguru import logger
from app.db.session import SessionLocal
import app.db.base  # noqa: F401
from app.db.models.assessment import Assignment, AssignmentQuestion, AssignmentSubmission, Concept
from app.services.assignment_service import (
    get_assignment_context,
    generate_mcq_set,
    grade_mcq_submission,
    overall_feedback,
)


def _concept_names(db, project_id: uuid.UUID, concept_id_strs: list) -> tuple[list, dict]:
    concepts = db.query(Concept).filter(
        Concept.project_id == project_id,
        Concept.id.in_(concept_id_strs),
    ).all()
    return [c.name for c in concepts], {c.name: c for c in concepts}


def generate_assignment_questions(state: dict) -> dict:
    """Generate MCQ rows for the assignment. Idempotent: clears stale questions first."""
    assignment_id = state.get("assignment_id", "?")
    logger.info(f"[assignment.generate] assignment={assignment_id} entry")
    db = SessionLocal()
    try:
        try:
            auuid = uuid.UUID(state["assignment_id"])
            pid = uuid.UUID(state["project_id"])
        except (KeyError, ValueError):
            return {"error": "Invalid assignment or project id"}

        assignment = db.get(Assignment, auuid)
        if assignment is None:
            return {"error": "Assignment not found"}
        if assignment.status not in ("generating", "draft"):
            return {"error": f"Assignment is {assignment.status}, cannot generate"}

        concept_id_strs = [str(c) for c in (state.get("concept_ids") or [])]
        if not concept_id_strs:
            return {"error": "No concepts selected"}
        concept_names, concept_by_name = _concept_names(db, pid, concept_id_strs)
        if not concept_names:
            return {"error": "Some concepts do not belong to this project"}

        num_questions = max(1, min(int(state.get("num_questions") or 5), 50))

        # Idempotency: drop stale questions so retries never duplicate.
        db.query(AssignmentQuestion).filter(AssignmentQuestion.assignment_id == auuid).delete()
        db.flush()

        context = get_assignment_context(db, str(pid), ", ".join(concept_names))
        mcqs = generate_mcq_set(concept_names, context, num_questions)
        if not mcqs:
            raise ValueError("Question generation returned no questions")

        for i, mcq in enumerate(mcqs):
            concept = concept_by_name.get(concept_names[i % len(concept_names)])
            db.add(AssignmentQuestion(
                assignment_id=auuid,
                concept_id=concept.id if concept else None,
                question_text=mcq["question_text"],
                options=mcq["options"],
                correct_answer=mcq["correct_answer"],
            ))
        assignment.status = "ready"
        db.commit()
        logger.success(f"[assignment.generate] assignment={assignment_id} ready with {len(mcqs)} questions")
        return {"error": ""}
    except Exception as e:
        db.rollback()
        logger.error(f"[assignment.generate] assignment={assignment_id} failed: {e}")
        return {"error": f"Failed to generate assignment: {e}"}
    finally:
        db.close()


def grade_assignment_submission(state: dict) -> dict:
    """Auto-grade answers and persist submission + feedback. Idempotent."""
    assignment_id = state.get("assignment_id", "?")
    logger.info(f"[assignment.grade] assignment={assignment_id} entry")
    db = SessionLocal()
    try:
        try:
            auuid = uuid.UUID(state["assignment_id"])
            pid = uuid.UUID(state["project_id"])
        except (KeyError, ValueError):
            return {"error": "Invalid assignment or project id"}

        assignment = db.get(Assignment, auuid)
        if assignment is None:
            return {"error": "Assignment not found"}

        # Idempotency: a submission row only ever exists once grading committed.
        existing = db.query(AssignmentSubmission).filter(
            AssignmentSubmission.assignment_id == auuid,
        ).first()
        if existing:
            logger.info(f"[assignment.grade] assignment={assignment_id} already graded, skipping")
            return {"score": existing.score, "total": existing.total, "error": ""}

        questions = db.query(AssignmentQuestion).filter(
            AssignmentQuestion.assignment_id == auuid
        ).order_by(AssignmentQuestion.created_at).all()
        if not questions:
            return {"error": "Assignment has no questions"}

        valid_ids = {str(q.id) for q in questions}
        answers = {str(k): str(v) for k, v in ((state.get("answers") or {}).items())}
        if set(answers) - valid_ids:
            return {"error": "Answers contain unknown question IDs"}

        q_dicts = [{"id": str(q.id), "correct_answer": q.correct_answer} for q in questions]
        score, total, per_question = grade_mcq_submission(q_dicts, answers)

        concept_names = [c.name for c in db.query(Concept).filter(
            Concept.project_id == pid,
            Concept.id.in_([str(c) for c in (assignment.concept_ids or [])]),
        ).all()] or ["this topic"]
        full_q = [{"id": str(q.id), "question_text": q.question_text} for q in questions]
        feedback = {
            "per_question": per_question,
            "overall": overall_feedback(concept_names, score, total, per_question, full_q),
        }

        submission = AssignmentSubmission(
            assignment_id=auuid,
            user_response="",
            answers=answers,
            score=float(score),
            total=total,
            feedback=feedback,
        )
        db.add(submission)

        # NOTE: assignments intentionally do NOT touch Concept mastery.
        # Mastery moves only via quizzes and the AI tutor.
        assignment.status = "submitted"
        db.commit()
        logger.success(f"[assignment.grade] assignment={assignment_id} score={score}/{total}")
        return {"score": float(score), "total": total, "error": ""}
    except Exception as e:
        db.rollback()
        logger.error(f"[assignment.grade] assignment={assignment_id} failed: {e}")
        return {"error": f"Failed to evaluate submission: {e}"}
    finally:
        db.close()


def assignment_error(state: dict) -> dict:
    """Terminal node: mark the assignment failed so polling stops."""
    assignment_id = state.get("assignment_id", "?")
    logger.error(f"[assignment.error] assignment={assignment_id} err={state.get('error')}")
    db = SessionLocal()
    try:
        try:
            assignment = db.get(Assignment, uuid.UUID(state["assignment_id"]))
            if assignment is not None and assignment.status == "generating":
                assignment.status = "failed"
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
    return {}


def route_entry(state: dict) -> str:
    """Answers present -> grade path, otherwise generate path."""
    if state.get("answers"):
        return "grade_submission"
    return "generate_questions"
