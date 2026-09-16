import json
import uuid
from datetime import datetime
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage
from app.db.session import SessionLocal
import app.db.base  # noqa: F401
from app.db.models.assessment import Quiz, QuizQuestion, Concept
from app.schemas.quiz import OpenEndedEvaluation
from app.tasks.celery_app import celery_app
from app.ai.llm import get_llm


@celery_app.task(name="quiz.evaluate", bind=True, max_retries=3)
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
            llm = get_llm()
            last_err = None
            evaluation = None
            for attempt in range(3):
                try:
                    res = llm.invoke(
                        [
                            SystemMessage(
                                content="Evaluate the open-ended answer for accuracy, missing concepts, and reasoning. "
                                'Return ONLY JSON: {"score": integer 0-100, "feedback": "string", "missing_concepts": ["string"]}.'
                            ),
                            HumanMessage(
                                content=f"Question: {question.question_text}\nAnswer: {user_answer}"
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
        concept.mastery_level = round((float(concept.mastery_level) * 0.7) + (score * 0.3), 2)
        concept.last_assessed_at = datetime.utcnow()
        db.commit()
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
    llm = get_llm()
    last_err = None
    for attempt in range(3):
        try:
            res = llm.invoke(
                [
                    SystemMessage(
                        content="Evaluate the open-ended answer for accuracy, missing concepts, and reasoning. "
                        'Return ONLY JSON: {"score": integer 0-100, "feedback": "string", "missing_concepts": ["string"]}.'
                    ),
                    HumanMessage(content=f"Question: {question.question_text}\nAnswer: {user_answer}"),
                ]
            )
            raw = res.content.strip().replace("```json", "").replace("```", "").strip()
            return OpenEndedEvaluation(**json.loads(raw)).model_dump()
        except Exception as e:
            last_err = e
            logger.warning(f"[quiz.eval_one] retry {attempt + 1}/3: {e}")
    raise last_err or RuntimeError("open-ended evaluation failed")


@celery_app.task(name="quiz.generate_batch", bind=True, max_retries=2)
def generate_batch_task(self, quiz_id: str, num_questions: int = 5) -> str:
    logger.info(f"[quiz.batch_task] quiz={quiz_id} n={num_questions} entry")
    db = SessionLocal()
    try:
        quiz = db.get(Quiz, uuid.UUID(quiz_id))
        if quiz is None:
            return "failed:not-found"
        project_id, goal = str(quiz.project_id), quiz.goal or ""
        db.close()
        from app.ai.quiz_graph import generate_quiz_batch

        ids = generate_quiz_batch(project_id, quiz_id, goal, max(1, min(num_questions, 10)))
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
            if not (q.user_answer or "").strip() or q.evaluation is not None:
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
