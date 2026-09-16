"""Async assignment tasks: run the assignment LangGraph in the background.

API flow: create row (generating) -> task -> ready; submit answers
(evaluating) -> task -> submitted. Frontend polls the detail endpoint.
"""
import asyncio
import uuid
from loguru import logger
from app.db.session import SessionLocal
import app.db.base  # noqa: F401
from app.db.models.assessment import Assignment
from app.tasks.celery_app import celery_app


def _run_graph(state: dict, thread_id: str) -> dict:
    from app.ai.graphs.assignment_graph import assignment_app

    return asyncio.run(
        assignment_app.ainvoke(state, config={"configurable": {"thread_id": thread_id}})
    )


@celery_app.task(name="assignment.generate_batch", bind=True, max_retries=2)
def generate_assignment_task(self, assignment_id: str, num_questions: int = 5) -> str:
    logger.info(f"[assignment.task.generate] assignment={assignment_id} n={num_questions} entry")
    db = SessionLocal()
    try:
        try:
            auuid = uuid.UUID(assignment_id)
        except ValueError:
            return "failed:invalid-id"
        assignment = db.get(Assignment, auuid)
        if assignment is None:
            return "failed:not-found"
        if assignment.status != "generating":
            return f"skipped:{assignment.status}"
        project_id = str(assignment.project_id)
        concept_ids = [str(c) for c in (assignment.concept_ids or [])]
        title = assignment.title or ""
        db.close()
        result = _run_graph(
            {
                "assignment_id": assignment_id,
                "project_id": project_id,
                "concept_ids": concept_ids,
                "title": title,
                "num_questions": max(1, min(int(num_questions or 5), 10)),
                "answers": {},
            },
            thread_id=f"assignment-generate-{assignment_id}",
        )
        if result.get("error"):
            raise RuntimeError(result["error"])
        return "ready"
    except Exception as e:
        logger.error(f"[assignment.task.generate] assignment={assignment_id} failed: {e}")
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
def evaluate_assignment_task(self, assignment_id: str, answers: dict) -> str:
    logger.info(f"[assignment.task.evaluate] assignment={assignment_id} entry")
    db = SessionLocal()
    try:
        try:
            auuid = uuid.UUID(assignment_id)
        except ValueError:
            return "failed:invalid-id"
        assignment = db.get(Assignment, auuid)
        if assignment is None:
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
        return f"submitted:{result.get('score', 0)}/{result.get('total', 0)}"
    except Exception as e:
        logger.error(f"[assignment.task.evaluate] assignment={assignment_id} failed: {e}")
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
