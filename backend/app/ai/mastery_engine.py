"""Hybrid adaptive engine: DB holds scores, LLM is the brain, app does the math.

LangSmith tracing is automatic via LANGCHAIN_TRACING_V2 / LANGCHAIN_API_KEY /
LANGCHAIN_PROJECT env vars picked up by LangChain.
"""
import json
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage
from app.ai.llm import get_llm
from app.schemas.mastery import (
    SelectorDecision,
    GeneratedQuestion,
    EvaluatorVerdict,
    Recommendation,
)


def _strict_json(system: str, human: str, model_cls, label: str):
    """Invoke the LLM and parse strict JSON into a Pydantic model (3 tries)."""
    llm = get_llm()
    last_err = None
    for attempt in range(3):
        try:
            res = llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
            raw = res.content.strip().replace("```json", "").replace("```", "").strip()
            return model_cls(**json.loads(raw))
        except Exception as e:
            last_err = e
            logger.warning(f"[mastery_engine:{label}] parse retry {attempt + 1}/3: {e}")
    raise last_err or RuntimeError(f"{label} failed")


def select_next_concept(mastery_state: list) -> SelectorDecision:
    state_json = json.dumps(mastery_state)
    logger.info(f"[mastery_engine:selector] {len(mastery_state)} concepts in state")
    try:
        return _strict_json(
            "You are an adaptive learning engine. Here is the user's current mastery "
            f"state for various concepts: {state_json}. Your goal is to select ONE "
            "concept to test next to maximize learning. DO NOT simply pick an easy "
            "question if they got the last one wrong. Use the qualitative feedback "
            "to isolate their specific gap. Target concepts where the score is "
            "between 30 and 70 (the zone of proximal development), unless they "
            "recently read material related to a specific concept. "
            "Concept names MUST stay short topic noun phrases — copy a name from "
            "the state verbatim, never invent sentences. Output a JSON object with "
            "keys: `concept` (name copied from the state), `question_type` "
            "(\"MCQ\" or \"OPEN_ENDED\"), `difficulty` (\"Easy\", \"Medium\" or "
            "\"Hard\"), `reasoning` (why you chose this concept and type).",
            f"Mastery state: {state_json}",
            SelectorDecision,
            "selector",
        )
    except Exception as e:
        logger.error(f"[mastery_engine:selector] failed: {e}")
        raise


def generate_question(concept: str, question_type: str, difficulty: str, context: str = "") -> GeneratedQuestion:
    logger.info(f"[mastery_engine:generator] concept={concept} type={question_type} difficulty={difficulty}")
    grounding = f"\nGround your question strictly in this material:\n{context}" if context else ""
    try:
        q = _strict_json(
            f"You are a quiz generator. Generate a {difficulty} difficulty {question_type} "
            f"question for the concept: '{concept}'. Requirements: If MCQ: Provide "
            "exactly 4 plausible options and the correct answer. If OPEN_ENDED: "
            "Provide a scenario-based question. Output a JSON object with keys: "
            "`question_text`, `options` (array of strings if MCQ, empty array if "
            "OPEN_ENDED), `correct_answer` (correct option string if MCQ, or a brief "
            "ideal answer if OPEN_ENDED).{grounding}",
            f"Concept: {concept}",
            GeneratedQuestion,
            "generator",
        )
        if question_type == "MCQ" and len(q.options) != 4:
            raise ValueError("MCQ must have exactly 4 options")
        return q
    except Exception as e:
        logger.error(f"[mastery_engine:generator] failed: {e}")
        raise


def evaluate_open_answer(question_text: str, ideal_answer: str, user_answer: str) -> EvaluatorVerdict:
    logger.info("[mastery_engine:evaluator] grading open-ended answer")
    try:
        return _strict_json(
            "You are an expert grader. Evaluate the user's answer. "
            f"Question: {question_text} Ideal Answer: {ideal_answer} "
            f"User's Answer: {user_answer} Evaluate based on: understanding, "
            "accuracy, relevance, key concepts covered, missing concepts, and "
            "reasoning. Feedback must explain what the learner understood and what "
            "is missing. Do not return only a numerical score. Output a JSON object "
            "with keys: `is_correct` (boolean), `score_delta` (integer from -15 to "
            "+15 based on quality), `feedback` (short, 1-2 sentence qualitative text).",
            f"Question: {question_text}\nUser's Answer: {user_answer}",
            EvaluatorVerdict,
            "evaluator",
        )
    except Exception as e:
        logger.error(f"[mastery_engine:evaluator] failed: {e}")
        raise


def recommend_next(mastery_state: list, recent_history: list) -> Recommendation:
    logger.info("[mastery_engine:recommender] generating recommendation")
    try:
        return _strict_json(
            "You are an educational tutor. Based on the following user data, "
            "generate a personalized recommendation for what they should study next. "
            "Be encouraging, specific, and reference their recent activity. "
            f"User Mastery State: {json.dumps(mastery_state)} Recent Quiz History: "
            f"{json.dumps(recent_history)} The purpose is to answer: What should I "
            "do next? Output a JSON object with keys: `growth_summary` (brief text "
            "identifying areas that are Improving, Stable, or Requiring Attention), "
            "`recommendation_text` (specific next step).",
            f"Mastery: {json.dumps(mastery_state)}\nHistory: {json.dumps(recent_history)}",
            Recommendation,
            "recommender",
        )
    except Exception as e:
        logger.error(f"[mastery_engine:recommender] failed: {e}")
        raise
