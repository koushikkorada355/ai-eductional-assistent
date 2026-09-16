import json
import random
import uuid
from datetime import datetime
from loguru import logger
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.ai.state import QuizState
from app.ai.llm import get_llm
from app.config import settings
from app.db.session import SessionLocal
import app.db.base  # noqa: F401
from app.db.models.assessment import Concept, Quiz, QuizQuestion
from app.db.models.document import DocumentChunk
from app.schemas.quiz import MCQQuestion, OpenEndedEvaluation
from app.db.checkpointer import checkpointer

MAX_QUESTIONS = 5


def _pid(value: str) -> uuid.UUID:
    return uuid.UUID(value)


def concept_name_for_eval(question, state: dict) -> str:
    if state.get("selected_concept"):
        return state["selected_concept"]
    try:
        if question.concept_id:
            db = SessionLocal()
            try:
                c = db.get(Concept, question.concept_id)
                return c.name if c else ""
            finally:
                db.close()
    except Exception:
        pass
    return ""


def _rag_context(db, project_id: str, query: str, limit: int = 5) -> str:
    """Top-k project-filtered chunks for a query. Empty string on failure."""
    try:
        emb = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-001",
            google_api_key=settings.GOOGLE_API_KEY,
            output_dimensionality=768,
        )
        qv = emb.embed_query(query)
        chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.project_id == _pid(project_id))
            .order_by(DocumentChunk.embedding.cosine_distance(qv))
            .limit(limit)
            .all()
        )
        return "\n".join(c.content[:1200] for c in chunks)[:6000]
    except Exception as e:
        logger.warning(f"[quiz.rag] retrieval failed: {e}")
        return ""


def _craft_question(concept: str, context: str, qtype: str) -> tuple:
    """Returns (question_text, options, correct_answer). Falls back deterministically."""
    llm = get_llm()
    for attempt in range(3):
        try:
            if qtype == "multiple_choice":
                res = llm.invoke(
                    [
                        SystemMessage(
                            content="Generate a multiple-choice question strictly about the target concept, "
                            "grounded in the context. Return ONLY JSON: "
                            '{"question_text": "...", "options": ["A","B","C","D"], "correct_answer": "..."}.'
                        ),
                        HumanMessage(content=f"Concept: {concept}\nContext:\n{context}"),
                    ]
                )
                raw = res.content.strip().replace("```json", "").replace("```", "").strip()
                validated = MCQQuestion(**json.loads(raw))
                return validated.question_text, validated.options, validated.correct_answer
            res = llm.invoke(
                [
                    SystemMessage(
                        content="Generate one open-ended question strictly about the target concept, "
                        "grounded in the context. Return ONLY the question text, no JSON."
                    ),
                    HumanMessage(content=f"Concept: {concept}\nContext:\n{context}"),
                ]
            )
            text = res.content.strip()
            if not text:
                raise ValueError("empty question")
            return text, None, None
        except Exception as e:
            logger.warning(f"[quiz.craft] retry {attempt + 1}/3: {e}")
    snippet = (context[:160] + "...") if context else "your uploaded materials"
    return f"What is the key idea of '{concept}'? Explain using: {snippet}", None, None


def select_concepts_for_goal(project_id: str, goal: str, n: int) -> list:
    """Weakest-first concepts re-ranked for relevance to the quiz goal."""
    db = SessionLocal()
    try:
        concepts = (
            db.query(Concept)
            .filter(Concept.project_id == _pid(project_id))
            .order_by(Concept.mastery_level.asc(), Concept.last_assessed_at.asc().nullsfirst())
            .limit(max(n * 3, 10))
            .all()
        )
        if not concepts:
            return []
        if not (goal or "").strip() or len(concepts) <= n:
            return concepts[:n]
        try:
            llm = get_llm()
            res = llm.invoke(
                [
                    SystemMessage(
                        content="Given the quiz goal and the concept list, return ONLY a JSON list of "
                        f"the {n} most relevant concept names, e.g. [\"A\", \"B\"]. No other text."
                    ),
                    HumanMessage(
                        content=f"Goal: {goal}\nConcepts: {[c.name for c in concepts]}"
                    ),
                ]
            )
            raw = res.content.strip().replace("```json", "").replace("```", "").strip()
            wanted = json.loads(raw)
            by_name = {c.name: c for c in concepts}
            picked = [by_name[w] for w in wanted if w in by_name]
            for c in concepts:
                if len(picked) >= n:
                    break
                if c not in picked:
                    picked.append(c)
            return picked[:n]
        except Exception as e:
            logger.warning(f"[quiz.select] goal ranking failed, using weakest-first: {e}")
            return concepts[:n]
    finally:
        db.close()


def generate_quiz_batch(project_id: str, quiz_id: str, goal: str, n: int) -> list:
    """Generate N distinct grounded questions upfront. Returns question-id strings."""
    concepts = select_concepts_for_goal(project_id, goal or "", n)
    if not concepts:
        raise ValueError("No concepts found. Upload PDFs first.")
    db = SessionLocal()
    try:
        goal_context = _rag_context(db, project_id, goal or concepts[0].name)
        ids: list[str] = []
        for i in range(n):
            concept = concepts[i % len(concepts)]
            qtype = "multiple_choice" if i % 2 == 0 else "open_ended"
            context = _rag_context(db, project_id, concept.name) or goal_context
            text, options, correct = _craft_question(concept.name, context, qtype)
            if qtype == "multiple_choice" and (not options or not correct):
                text, options, correct = _craft_question(concept.name, context, "open_ended")
                qtype = "open_ended"
            exists = (
                db.query(QuizQuestion)
                .filter(QuizQuestion.quiz_id == _pid(quiz_id), QuizQuestion.question_text == text)
                .first()
            )
            if exists:
                ids.append(str(exists.id))
                continue
            qq = QuizQuestion(
                quiz_id=_pid(quiz_id),
                concept_id=concept.id,
                question_type=qtype,
                question_text=text,
                options=options,
                correct_answer=correct,
            )
            db.add(qq)
            db.flush()
            ids.append(str(qq.id))
        db.commit()
        logger.success(f"[quiz.batch] quiz={quiz_id} generated {len(ids)} questions")
        return ids
    finally:
        db.close()


def assess_mastery(state: dict) -> dict:
    project_id = state.get("project_id", "?")
    logger.info(f"[quiz.assess] project_id={project_id} quiz={state.get('quiz_id')} entry")
    db = SessionLocal()
    try:
        concepts = (
            db.query(Concept)
            .filter(Concept.project_id == _pid(state["project_id"]))
            .order_by(Concept.mastery_level.asc(), Concept.last_assessed_at.asc().nullsfirst())
            .all()
        )
        if not concepts:
            logger.warning(f"[quiz.assess] no concepts project={project_id}")
            return {"error": "No concepts found. Upload PDFs first.", "concepts_to_test": []}
        top = concepts[0]
        logger.info(f"[quiz.assess] selected concept={top.name} mastery={top.mastery_level}")
        return {
            "selected_concept": top.name,
            "selected_concept_id": str(top.id),
            "concepts_to_test": [c.name for c in concepts[:5]],
            "error": "",
        }
    finally:
        db.close()


def quiz_error(state: dict) -> dict:
    logger.error(f"[quiz.error] project={state.get('project_id')} err={state.get('error')}")
    return {"messages": [AIMessage(content=state.get("error") or "Quiz unavailable.")]}


def generate_question(state: dict) -> dict:
    project_id = state["project_id"]
    concept = state.get("selected_concept", "")
    logger.info(f"[quiz.generate] project={project_id} concept={concept} entry")
    db = SessionLocal()
    try:
        context = _rag_context(db, project_id, concept)
        qtype = random.choice(["multiple_choice", "open_ended"])
        question_text, options, correct = _craft_question(concept, context, qtype)
        if qtype == "multiple_choice" and (not options or not correct):
            question_text, options, correct = _craft_question(concept, context, "open_ended")
            qtype = "open_ended"

        # Idempotency: avoid duplicate question text for this quiz+concept
        quiz_uuid = _pid(state["quiz_id"])
        concept_uuid = _pid(state["selected_concept_id"]) if state.get("selected_concept_id") else None
        existing = (
            db.query(QuizQuestion)
            .filter(QuizQuestion.quiz_id == quiz_uuid, QuizQuestion.question_text == question_text)
            .first()
        )
        if existing:
            logger.info(f"[quiz.generate] duplicate skipped, reusing {existing.id}")
            qq = existing
        else:
            qq = QuizQuestion(
                quiz_id=quiz_uuid,
                concept_id=concept_uuid,
                question_type=qtype,
                question_text=question_text,
                options=options,
                correct_answer=correct,
                user_answer=None,
                evaluation=None,
            )
            db.add(qq)
            db.commit()
            db.refresh(qq)

        asked = int(state.get("questions_asked") or 0) + 1
        logger.info(f"[quiz.generate] done qid={qq.id} type={qtype} asked={asked}")
        # Interrupt point: return question to user via messages
        msg = f"{question_text}" + (f"\nOptions: {', '.join(options)}" if options else "")
        return {
            "current_question": question_text,
            "current_question_id": str(qq.id),
            "question_type": qtype,
            "questions_asked": asked,
            "messages": [AIMessage(content=msg)],
        }
    finally:
        db.close()


def evaluate_answer(state: dict) -> dict:
    qid = state.get("current_question_id", "?")
    logger.info(f"[quiz.evaluate_node] qid={qid} entry")
    db = SessionLocal()
    try:
        question = db.get(QuizQuestion, _pid(qid)) if qid else None
        if question is None:
            return {"evaluation": {"score": 0, "feedback": "Question not found.", "missing_concepts": []}}
        user_answer = state.get("user_answer") or ""
        question.user_answer = user_answer

        if question.question_type == "multiple_choice":
            u = (user_answer or "").strip()
            c = (question.correct_answer or "").strip()
            # Tolerant match: exact (case-insensitive) or leading-letter ("A" vs "A. Chlorophyll a")
            correct = u.lower() == c.lower() or (
                bool(u) and bool(c) and (len(u) == 1 or len(c) == 1) and u[0].lower() == c[0].lower()
            ) or (bool(u) and bool(c) and (u.lower().startswith(c.lower()) or c.lower().startswith(u.lower())))
            score = 100 if correct else 0
            llm = get_llm()
            try:
                res = llm.invoke(
                    [
                        SystemMessage(content="In exactly one sentence, explain why the correct answer is right. No extra text."),
                        HumanMessage(content=f"Q: {question.question_text}\nCorrect: {question.correct_answer}"),
                    ]
                )
                expl = res.content.strip()
            except Exception:
                expl = f"The correct answer is '{question.correct_answer}'."
            evaluation = {
                "score": score,
                "feedback": f"{'Correct. ' if correct else 'Incorrect. '}{expl}",
                "missing_concepts": [] if correct else [concept_name_for_eval(question, state)],
            }
            question.evaluation = evaluation
            db.commit()
        else:
            # Async: dispatch celery so API returns instantly; mark pending
            try:
                from app.tasks.quiz_tasks import evaluate_quiz_task

                evaluate_quiz_task.delay(str(question.id), user_answer)
            except Exception as ce:
                logger.warning(f"[quiz.evaluate_node] celery dispatch failed, continuing pending: {ce}")
            evaluation = {"score": 0, "feedback": "Evaluation in progress.", "missing_concepts": [], "pending": True}
            db.commit()
        logger.info(f"[quiz.evaluate_node] qid={qid} score={evaluation.get('score')}")
        return {"evaluation": evaluation}
    finally:
        db.close()


def update_mastery(state: dict) -> dict:
    qid = state.get("current_question_id", "?")
    logger.info(f"[quiz.mastery] qid={qid} entry")
    # Delegate math to celery task for consistency (sync fallback if needed)
    try:
        from app.tasks.quiz_tasks import update_mastery_from_quiz_task

        # Only run sync update for MCQ (open-ended pending until celery finishes)
        if state.get("question_type") == "multiple_choice":
            update_mastery_from_quiz_task(str(qid) if qid else "")
    except Exception as e:
        logger.warning(f"[quiz.mastery] dispatch failed: {e}")
    db = SessionLocal()
    try:
        if qid:
            try:
                question = db.get(QuizQuestion, _pid(qid))
                if question and question.concept_id:
                    concept = db.get(Concept, question.concept_id)
                    if concept:
                        concept.last_assessed_at = datetime.utcnow()
                        db.commit()
            except Exception:
                db.rollback()
    finally:
        db.close()
    logger.info(f"[quiz.mastery] qid={qid} done")
    return {}


def route_after_assess(state: dict) -> str:
    if state.get("error"):
        return "quiz_error"
    return "generate_question"


def route_loop(state: dict) -> str:
    asked = int(state.get("questions_asked") or 0)
    if asked >= MAX_QUESTIONS:
        return "end"
    return "assess_mastery"


workflow = StateGraph(QuizState)
workflow.add_node("assess_mastery", assess_mastery)
workflow.add_node("generate_question", generate_question)
workflow.add_node("evaluate_answer", evaluate_answer)
workflow.add_node("update_mastery", update_mastery)
workflow.add_node("quiz_error", quiz_error)
workflow.add_edge(START, "assess_mastery")
workflow.add_conditional_edges("assess_mastery", route_after_assess)
workflow.add_edge("generate_question", END)  # interrupt: return question to user
workflow.add_edge("evaluate_answer", "update_mastery")
workflow.add_conditional_edges("update_mastery", route_loop, {"assess_mastery": "assess_mastery", "end": END})
workflow.add_edge("quiz_error", END)

quiz_app = workflow.compile(checkpointer=checkpointer)
