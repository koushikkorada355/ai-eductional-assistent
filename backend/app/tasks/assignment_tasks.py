"""Async assignment tasks: run the assignment LangGraph in the background.

API flow: create row (generating) -> task -> ready; submit answers
(evaluating) -> task -> submitted. Frontend polls the detail endpoint.
"""
import asyncio
import time
import uuid
from loguru import logger
from app.db.session import SessionLocal
import app.db.base  # noqa: F401
from app.db.models.assessment import Assignment
from app.tasks.celery_app import celery_app
from app.services.ai_usage_service import track_ai_call


def _tag(name: str, jid: str) -> str:
    return f"[JOB {name}|id={str(jid)[:8]}]"


def _run_graph(state: dict, thread_id: str) -> dict:
    from app.ai.graphs.assignment_graph import assignment_app

    return asyncio.run(
        assignment_app.ainvoke(state, config={"configurable": {"thread_id": thread_id}})
    )


@celery_app.task(name="assignment.generate_batch", bind=True, max_retries=2)
@track_ai_call("assignment_generation")
def generate_assignment_task(self, assignment_id: str, num_questions: int = 5) -> str:
    t0 = time.monotonic()
    tag = _tag("assignment.generate", assignment_id)
    logger.info(f"{tag} received n={num_questions}")
    db = SessionLocal()
    try:
        try:
            auuid = uuid.UUID(assignment_id)
        except ValueError:
            logger.error(f"{tag} invalid uuid")
            return "failed:invalid-id"
        assignment = db.get(Assignment, auuid)
        if assignment is None:
            logger.error(f"{tag} not found in DB")
            return "failed:not-found"
        if assignment.status != "generating":
            logger.info(f"{tag} skipped status={assignment.status}")
            return f"skipped:{assignment.status}"
        project_id = str(assignment.project_id)
        concept_ids = [str(c) for c in (assignment.concept_ids or [])]
        title = assignment.title or ""
        db.close()
        logger.info(f"{tag} phase=graph start project={project_id[:8]} concepts={len(concept_ids)}")
        result = _run_graph(
            {
                "assignment_id": assignment_id,
                "project_id": project_id,
                "concept_ids": concept_ids,
                "title": title,
                "num_questions": max(1, min(int(num_questions or 5), 50)),
                "answers": {},
            },
            thread_id=f"assignment-generate-{assignment_id}",
        )
        if result.get("error"):
            raise RuntimeError(result["error"])
        logger.success(f"{tag} DONE in {time.monotonic() - t0:.1f}s")
        return "ready"
    except Exception as e:
        logger.opt(exception=True).error(f"{tag} FAILED after {time.monotonic() - t0:.1f}s: {type(e).__name__}: {e}")
        try:
            raise self.retry(exc=e, countdown=15)
        except self.MaxRetriesExceededError:
            # Terminal: mark failed so polling stops.
            try:
                db2 = SessionLocal()
                try:
                    a = db2.get(Assignment, uuid.UUID(assignment_id))
                    if a is not None and a.status == "generating":
                        a.status = "failed"
                        db2.commit()
                finally:
                    db2.close()
            except Exception:
                pass
            return f"failed:{e}"
    finally:
        try:
            db.close()
        except Exception:
            pass


@celery_app.task(name="assignment.evaluate_submission", bind=True, max_retries=2)
@track_ai_call("assignment_evaluation")
def evaluate_assignment_task(self, assignment_id: str, answers: dict) -> str:
    t0 = time.monotonic()
    tag = _tag("assignment.evaluate", assignment_id)
    logger.info(f"{tag} received answers={len(answers or {})}")
    db = SessionLocal()
    try:
        try:
            auuid = uuid.UUID(assignment_id)
        except ValueError:
            logger.error(f"{tag} invalid uuid")
            return "failed:invalid-id"
        assignment = db.get(Assignment, auuid)
        if assignment is None:
            logger.error(f"{tag} not found in DB")
            return "failed:not-found"
        project_id = str(assignment.project_id)
        concept_ids = [str(c) for c in (assignment.concept_ids or [])]
        db.close()
        result = _run_graph(
            {
                "assignment_id": assignment_id,
                "project_id": project_id,
                "concept_ids": concept_ids,
                "answers": answers or {},
            },
            thread_id=f"assignment-evaluate-{assignment_id}",
        )
        if result.get("error"):
            raise RuntimeError(result["error"])
        logger.success(f"{tag} DONE in {time.monotonic() - t0:.1f}s score={result.get('score', 0)}/{result.get('total', 0)}")
        return f"submitted:{result.get('score', 0)}/{result.get('total', 0)}"
    except Exception as e:
        logger.opt(exception=True).error(f"{tag} FAILED after {time.monotonic() - t0:.1f}s: {type(e).__name__}: {e}")
        try:
            raise self.retry(exc=e, countdown=15)
        except self.MaxRetriesExceededError:
            # Terminal: reopen the assignment so the user can retry (answers
            # live in the task args / frontend state, nothing partial persists).
            try:
                db2 = SessionLocal()
                try:
                    a = db2.get(Assignment, uuid.UUID(assignment_id))
                    if a is not None and a.status == "evaluating":
                        a.status = "ready"
                        db2.commit()
                finally:
                    db2.close()
            except Exception:
                pass
            return f"failed:{e}"
    finally:
        try:
            db.close()
        except Exception:
            pass
