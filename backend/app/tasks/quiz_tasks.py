import json
import uuid
from datetime import datetime
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage
from app.db.session import SessionLocal
import app.db.base  # noqa: F401
from app.db.models.assessment import Quiz, QuizQuestion, Concept
from app.db.models.project import Project
from app.db.models.space import Space
from app.schemas.quiz import OpenEndedEvaluation
from app.tasks.celery_app import celery_app
from app.ai.llm import get_llm
from app.services.analytics_service import record_mastery_snapshot
from app.services.ai_usage_service import track_ai_call


# Answers that mean "no attempt": blank, whitespace-only, or an explicit
# no-answer token. These must always score 0 — never reach the LLM grader,
# which can otherwise award points for an empty response.
_NO_ANSWER_TOKENS = frozenset({
    "", "n/a", "na", "idk", "dont know", "don't know", "do not know",
    "no idea", "?", "-", "--", "...", "....", "no answer", "skip", "skipped",
})


def _is_blank_open_answer(text) -> bool:
    if text is None:
        return True
    s = str(text).strip()
    if not s:
        return True
    norm = " ".join(s.lower().split())
    if norm in _NO_ANSWER_TOKENS:
        return True
    # A single character carries no gradable content for open-ended.
    if len(s) < 2:
        return True
    return False


def _blank_open_evaluation() -> dict:
    return {
        "score": 0,
        "feedback": "No answer provided. Score 0 — write your own response to earn points.",
        "missing_concepts": [],
    }


@celery_app.task(name="quiz.evaluate", bind=True, max_retries=3)
@track_ai_call("quiz_evaluation")
def evaluate_quiz_task(self, quiz_question_id: str, user_answer: str) -> str:
    logger.info(f"[quiz.evaluate] question_id={quiz_question_id}")
    db = SessionLocal()
    try:
        qid = uuid.UUID(quiz_question_id)
        question = db.get(QuizQuestion, qid)
        if question is None:
            logger.error(f"[quiz.evaluate] not found {quiz_question_id}")
            return "failed:not-found"

        # Idempotency: already evaluated
        if question.evaluation is not None and question.user_answer == user_answer:
            return "skipped:already-evaluated"

        question.user_answer = user_answer
        db.commit()

        if question.question_type == "multiple_choice":
            u = (user_answer or "").strip()
            c = (question.correct_answer or "").strip()
            correct = u.lower() == c.lower() or (
                bool(u) and bool(c) and (len(u) == 1 or len(c) == 1) and u[0].lower() == c[0].lower()
            ) or (bool(u) and bool(c) and (u.lower().startswith(c.lower()) or c.lower().startswith(u.lower())))
            score = 100 if correct else 0
            evaluation = {
                "score": score,
                "feedback": f"{'Correct.' if correct else 'Incorrect.'} The right answer is '{question.correct_answer}'.",
                "missing_concepts": [] if correct else ["review-target-concept"],
            }
        else:
            # Blank / no-attempt answers are always 0 — never send to the LLM.
            if _is_blank_open_answer(user_answer):
                evaluation = _blank_open_evaluation()
            else:
                llm = get_llm()
                last_err = None
                evaluation = None
                for attempt in range(3):
                    try:
                        res = llm.invoke(
                            [
                                SystemMessage(
                                    content="Evaluate the open-ended answer for accuracy, missing concepts, and reasoning. "
                                    "Be strict: award points only for demonstrated correctness, never for effort or verbosity. "
                                    "An empty, off-topic, or 'I don't know' answer always scores 0. "
                                    'Return ONLY JSON: {"score": integer 0-100, "feedback": "string", "missing_concepts": ["string"]}.'
                                ),
                                HumanMessage(
                                    content=f"Question: {question.question_text}\nIdeal answer: {question.correct_answer}\nAnswer: {user_answer}"
                                ),
                            ]
                        )
                        raw = res.content.strip().replace("```json", "").replace("```", "").strip()
                        validated = OpenEndedEvaluation(**json.loads(raw))
                        evaluation = validated.model_dump()
                        break
                    except Exception as e:
                        last_err = e
                        logger.warning(f"[quiz.evaluate] retry {attempt + 1}/3 q={quiz_question_id}: {e}")
                if evaluation is None:
                    raise last_err or RuntimeError("evaluation failed")

        question.evaluation = evaluation
        db.commit()
        logger.success(f"[quiz.evaluate] q={quiz_question_id} score={evaluation.get('score')}")

        # chain mastery update
        update_mastery_from_quiz_task.delay(str(question.id))
        return f"evaluated:{evaluation.get('score')}"
    except Exception as e:
        db.rollback()
        logger.error(f"[quiz.evaluate] failed q={quiz_question_id}: {e}")
        try:
            raise self.retry(exc=e, countdown=10)
        except self.MaxRetriesExceededError:
            return f"failed:{e}"
    finally:
        db.close()


@celery_app.task(name="mastery.update_from_quiz")
def update_mastery_from_quiz_task(quiz_question_id: str) -> str:
    logger.info(f"[mastery.quiz] question_id={quiz_question_id}")
    db = SessionLocal()
    try:
        question = db.get(QuizQuestion, uuid.UUID(quiz_question_id))
        if question is None or question.concept_id is None or not question.evaluation:
            return "skipped:no-concept-or-eval"
        concept = db.get(Concept, question.concept_id)
        if concept is None:
            return "skipped:concept-gone"
        score = float((question.evaluation or {}).get("score", 0))
        score = max(0.0, min(100.0, score))
        old_mastery = float(concept.mastery_level)
        concept.mastery_level = round(old_mastery * 0.7 + score * 0.3, 2)
        concept.last_assessed_at = datetime.utcnow()
        concept_created = concept.created_at
        concept_id = concept.id
        new_mastery = concept.mastery_level
        db.commit()
        # Growth history (separate transaction; mastery math above unchanged).
        try:
            quiz = db.get(Quiz, question.quiz_id)
            project = db.get(Project, quiz.project_id) if quiz else None
            space = db.get(Space, project.space_id) if project else None
            record_mastery_snapshot(
                db,
                user_id=space.user_id if space else None,
                project_id=project.id if project else None,
                concept_id=concept_id,
                new_mastery=new_mastery,
                source="quiz",
                source_id=question.id,
                previous_mastery=old_mastery,
                baseline_at=concept_created,
            )
        except Exception as he:
            logger.warning(f"[mastery.quiz] history skipped q={quiz_question_id}: {he}")
        # Keep Project.overall_progress live (best-effort; never breaks mastery).
        try:
            from app.services.analytics_service import recompute_project_progress

            _quiz = db.get(Quiz, question.quiz_id)
            if _quiz is not None:
                recompute_project_progress(db, _quiz.project_id)
        except Exception as pe:
            logger.warning(f"[mastery.quiz] progress recompute skipped q={quiz_question_id}: {pe}")
        logger.success(f"[mastery.quiz] concept={concept.name} new={concept.mastery_level}")
        return f"updated:{concept.mastery_level}"
    except Exception as e:
        db.rollback()
        logger.error(f"[mastery.quiz] failed q={quiz_question_id}: {e}")
        return f"failed:{e}"
    finally:
        db.close()


def _tolerant_mcq_match(user_answer: str, correct_answer: str) -> bool:
    u = (user_answer or "").strip()
    c = (correct_answer or "").strip()
    if not u or not c:
        return False
    return (
        u.lower() == c.lower()
        or ((len(u) == 1 or len(c) == 1) and u[0].lower() == c[0].lower())
        or u.lower().startswith(c.lower())
        or c.lower().startswith(u.lower())
    )


def _evaluate_mcq(question: QuizQuestion, user_answer: str) -> dict:
    correct = _tolerant_mcq_match(user_answer, question.correct_answer)
    try:
        llm = get_llm()
        res = llm.invoke(
            [
                SystemMessage(content="In exactly one sentence, explain why the correct answer is right. No extra text."),
                HumanMessage(content=f"Q: {question.question_text}\nCorrect: {question.correct_answer}"),
            ]
        )
        expl = res.content.strip()
    except Exception:
        expl = f"The correct answer is '{question.correct_answer}'."
    return {
        "score": 100 if correct else 0,
        "feedback": f"{'Correct. ' if correct else 'Incorrect. '}{expl}",
        "missing_concepts": [],
    }


def _evaluate_open(question: QuizQuestion, user_answer: str) -> dict:
    # Blank / no-attempt answers are always 0 — never send to the LLM.
    if _is_blank_open_answer(user_answer):
        return _blank_open_evaluation()
    llm = get_llm()
    last_err = None
    for attempt in range(3):
        try:
            res = llm.invoke(
                [
                    SystemMessage(
                        content="Evaluate the open-ended answer for accuracy, missing concepts, and reasoning. "
                        "Be strict: award points only for demonstrated correctness, never for effort or verbosity. "
                        "An empty, off-topic, or 'I don't know' answer always scores 0. "
                        'Return ONLY JSON: {"score": integer 0-100, "feedback": "string", "missing_concepts": ["string"]}.'
                    ),
                    HumanMessage(content=f"Question: {question.question_text}\nIdeal answer: {question.correct_answer}\nAnswer: {user_answer}"),
                ]
            )
            raw = res.content.strip().replace("```json", "").replace("```", "").strip()
            return OpenEndedEvaluation(**json.loads(raw)).model_dump()
        except Exception as e:
            last_err = e
            logger.warning(f"[quiz.eval_one] retry {attempt + 1}/3: {e}")
    raise last_err or RuntimeError("open-ended evaluation failed")


@celery_app.task(name="quiz.generate_batch", bind=True, max_retries=2)
@track_ai_call("quiz_generation")
def generate_batch_task(self, quiz_id: str, num_mcq: int = 3, num_open: int = 2) -> str:
    logger.info(f"[quiz.batch_task] quiz={quiz_id} mcq={num_mcq} open={num_open} entry")
    db = SessionLocal()
    try:
        quiz = db.get(Quiz, uuid.UUID(quiz_id))
        if quiz is None:
            return "failed:not-found"
        project_id, goal = str(quiz.project_id), quiz.goal or ""
        db.close()
        from app.ai.nodes import generate_quiz_batch

        num_mcq = max(0, min(int(num_mcq), 10))
        num_open = max(0, min(int(num_open), 10))
        if num_mcq + num_open < 1 or num_mcq + num_open > 10:
            raise ValueError("Total questions (MCQs + open-ended) must be between 1 and 10")
        ids = generate_quiz_batch(project_id, quiz_id, goal, num_mcq, num_open)
        db = SessionLocal()
        quiz = db.get(Quiz, uuid.UUID(quiz_id))
        quiz.status = "in_progress"
        db.commit()
        logger.success(f"[quiz.batch_task] quiz={quiz_id} ready with {len(ids)} questions")
        return f"ready:{len(ids)}"
    except Exception as e:
        logger.error(f"[quiz.batch_task] quiz={quiz_id} failed: {e}")
        try:
            db2 = SessionLocal()
            try:
                quiz = db2.get(Quiz, uuid.UUID(quiz_id))
                if quiz is not None:
                    quiz.status = "failed"
                    db2.commit()
            finally:
                db2.close()
        except Exception:
            pass
        try:
            raise self.retry(exc=e, countdown=15)
        except self.MaxRetriesExceededError:
            return f"failed:{e}"
    finally:
        try:
            db.close()
        except Exception:
            pass


@celery_app.task(name="quiz.evaluate_submission", bind=True, max_retries=2)
def evaluate_submission_task(self, quiz_id: str) -> str:
    logger.info(f"[quiz.submit_task] quiz={quiz_id} entry")
    db = SessionLocal()
    try:
        quiz = db.get(Quiz, uuid.UUID(quiz_id))
        if quiz is None:
            return "failed:not-found"
        if quiz.status == "completed":
            return "skipped:already-completed"
        questions = (
            db.query(QuizQuestion)
            .filter(QuizQuestion.quiz_id == quiz.id)
            .order_by(QuizQuestion.created_at.asc())
            .all()
        )
        for q in questions:
            if q.evaluation is not None:
                continue
            # Unanswered or blank answers count as 0 — skipping them would
            # inflate the average (e.g. 2/5 answered correctly showing as 100).
            if q.user_answer is None:
                q.user_answer = ""
            if q.question_type != "multiple_choice" and _is_blank_open_answer(q.user_answer):
                q.evaluation = _blank_open_evaluation()
                db.commit()
                continue
            try:
                if q.question_type == "multiple_choice":
                    q.evaluation = _evaluate_mcq(q, q.user_answer)
                else:
                    q.evaluation = _evaluate_open(q, q.user_answer)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"[quiz.submit_task] eval failed q={q.id}: {e}")
                q.evaluation = {"score": 0, "feedback": "Evaluation failed. Please retry.", "missing_concepts": []}
                db.commit()
        db.expire_all()
        questions = (
            db.query(QuizQuestion)
            .filter(QuizQuestion.quiz_id == quiz.id)
            .all()
        )
        for q in questions:
            try:
                update_mastery_from_quiz_task(str(q.id))
            except Exception as e:
                logger.warning(f"[quiz.submit_task] mastery failed q={q.id}: {e}")
        quiz = db.get(Quiz, uuid.UUID(quiz_id))
        quiz.status = "completed"
        db.commit()
        from app.services.event_service import emit_event, owner_of_project, QUIZ_COMPLETED

        emit_event(
            db,
            type=QUIZ_COMPLETED,
            user_id=owner_of_project(db, quiz.project_id),
            project_id=quiz.project_id,
            text=f"Quiz '{quiz.name}' completed",
            event_key=f"quiz:{quiz.id}",
        )
        logger.success(f"[quiz.submit_task] quiz={quiz_id} completed")
        return "completed"
    except Exception as e:
        db.rollback()
        logger.error(f"[quiz.submit_task] quiz={quiz_id} failed: {e}")
        try:
            raise self.retry(exc=e, countdown=15)
        except self.MaxRetriesExceededError:
            return f"failed:{e}"
    finally:
        db.close()
