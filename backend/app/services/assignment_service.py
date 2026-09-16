"""Synchronous MCQ assignment service.

No Celery, no LangGraph: generation and grading run inline in the request.
"""
import json
import random
import re
from loguru import logger
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.llm import get_llm
from app.ai.prompts import ASSIGNMENT_MCQ_GENERATION_PROMPT, ASSIGNMENT_OVERALL_FEEDBACK_PROMPT
from app.schemas.quiz import MCQQuestion


def _is_fake_llm(llm) -> bool:
    return llm.__class__.__name__ == "FakeMessagesListChatModel"


def get_assignment_context(db: Session, project_id: str, query: str, limit: int = 5) -> str:
    """Project-filtered RAG context for grounding MCQs. Empty string on failure."""
    try:
        from app.ai.nodes.quiz_nodes import _rag_context
        return _rag_context(db, project_id, query, limit=limit)
    except Exception as e:
        logger.warning(f"[assignment.rag] retrieval failed: {e}")
        return ""


def _strip_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    return text


def _fallback_mcqs(concept_names: list[str], num_questions: int) -> list[dict]:
    """Deterministic MCQs so assignment creation works even without an LLM key."""
    items = []
    for i in range(num_questions):
        concept = concept_names[i % len(concept_names)]
        items.append({
            "question_text": f"Which statement best describes '{concept}'?",
            "options": [
                f"The core definition and purpose of {concept}",
                f"An unrelated concept with no link to {concept}",
                f"A common misconception about {concept}",
                f"A partially true but incomplete idea about {concept}",
            ],
            "correct_answer": f"The core definition and purpose of {concept}",
        })
    return items


def generate_mcq_set(concept_names: list[str], context: str, num_questions: int) -> list[dict]:
    """Generate num_questions validated MCQs. Raises ValueError on total failure."""
    if not concept_names:
        raise ValueError("No concepts selected")

    llm = get_llm()
    if _is_fake_llm(llm):
        logger.info("[assignment] no LLM key, using fallback MCQs")
        return _fallback_mcqs(concept_names, num_questions)

    concepts_str = ", ".join(concept_names)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            res = llm.invoke([
                SystemMessage(content="You generate exam MCQs. Return ONLY valid JSON, no other text."),
                HumanMessage(content=ASSIGNMENT_MCQ_GENERATION_PROMPT.format(
                    num_questions=num_questions,
                    concepts=concepts_str,
                    context=context or "(no material context available; use general knowledge of the concepts)",
                )),
            ])
            raw = _strip_fences(res.content)
            data = json.loads(raw)
            if isinstance(data, dict):
                data = data.get("questions", data.get("items", []))
            if not isinstance(data, list) or not data:
                raise ValueError("LLM did not return a question list")
            validated = [MCQQuestion(**q).model_dump() for q in data[:num_questions]]
            if len(validated) < num_questions:
                raise ValueError(f"Only {len(validated)} valid questions returned")
            # Ensure correct_answer matches an option exactly
            for q in validated:
                if q["correct_answer"] not in q["options"]:
                    raise ValueError("correct_answer does not match any option")
            # Shuffle options so the correct answer isn't always first
            for q in validated:
                random.shuffle(q["options"])
            logger.success(f"[assignment] generated {len(validated)} MCQs")
            return validated
        except Exception as e:
            last_error = e
            logger.warning(f"[assignment.generate] attempt {attempt + 1}/3 failed: {e}")

    logger.error(f"[assignment.generate] LLM failed, using fallback: {last_error}")
    return _fallback_mcqs(concept_names, num_questions)


def is_correct(user_answer: str, correct_answer: str) -> bool:
    """Tolerant MCQ match: exact (case-insensitive) or leading-letter/affix match."""
    u = (user_answer or "").strip()
    c = (correct_answer or "").strip()
    if not u or not c:
        return False
    if u.lower() == c.lower():
        return True
    if (len(u) == 1 or len(c) == 1) and u[0].lower() == c[0].lower():
        return True
    return u.lower().startswith(c.lower()) or c.lower().startswith(u.lower())


def grade_mcq_submission(questions: list, answers: dict[str, str]) -> tuple[int, int, list[dict]]:
    """Auto-grade synchronously. Returns (score, total, per_question results)."""
    results = []
    score = 0
    for q in questions:
        qid = str(q["id"])
        selected = (answers or {}).get(qid, "")
        correct = is_correct(selected, q["correct_answer"])
        if correct:
            score += 1
        results.append({
            "question_id": qid,
            "selected": selected,
            "correct_answer": q["correct_answer"],
            "is_correct": correct,
        })
    return score, len(questions), results


def overall_feedback(concept_names: list[str], score: int, total: int, results: list[dict], questions: list) -> str:
    """Short overall feedback, sync LLM call with computed fallback."""
    if total == 0:
        return "No questions to evaluate."
    if score == total:
        return f"Perfect score — {score}/{total}! You have a strong grasp of {', '.join(concept_names)}. Keep it up."
    if score == 0:
        return f"You scored 0/{total}. Review the material on {', '.join(concept_names)} and try again."

    lines = []
    by_id = {str(q["id"]): q for q in questions}
    for r in results:
        if not r["is_correct"]:
            q = by_id.get(r["question_id"], {})
            lines.append(f"Q: {q.get('question_text', '')} | Correct: {r['correct_answer']}")

    llm = get_llm()
    if _is_fake_llm(llm):
        return f"You scored {score}/{total}. Review the questions you missed and try again."
    try:
        res = llm.invoke([
            SystemMessage(content="You write short student feedback. Plain text only."),
            HumanMessage(content=ASSIGNMENT_OVERALL_FEEDBACK_PROMPT.format(
                score=score, total=total,
                concepts=", ".join(concept_names),
                results="\n".join(lines) or "(all correct)",
            )),
        ])
        text = (res.content or "").strip()
        return text or f"You scored {score}/{total}."
    except Exception as e:
        logger.warning(f"[assignment.feedback] LLM failed: {e}")
        return f"You scored {score}/{total}. Review the questions you missed and try again."
