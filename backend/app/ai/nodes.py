import json
import uuid
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.config import settings
from app.db.session import SessionLocal
from app.db.models.document import DocumentChunk
from app.ai.llm import get_llm
from app.schemas.quiz import ChatMasterySignal

REJECT_MESSAGE = "I cannot answer this based on the provided materials."

INTENT_GENERAL = "general"
INTENT_KNOWLEDGE = "knowledge"


async def detect_intent(state: dict) -> dict:
    logger.info(f"[tutor.intent] project_id={state.get('project_id', '?')} entry")
    llm = get_llm()
    try:
        res = await llm.ainvoke(
            [
                SystemMessage(
                    content="Classify the user's message. Output ONLY one word: "
                    f"'{INTENT_GENERAL}' if it is general conversation "
                    "(greeting, small talk, asking what you can do, thanks, goodbye), "
                    f"or '{INTENT_KNOWLEDGE}' if it asks about specific learning material or knowledge. "
                    "No other text."
                ),
                HumanMessage(content=state.get("user_question", "")),
            ]
        )
        label = res.content.strip().lower()
        intent = INTENT_GENERAL if INTENT_GENERAL in label else INTENT_KNOWLEDGE
    except Exception as e:
        logger.warning(f"[tutor.intent] classifier failed, defaulting to knowledge: {e}")
        intent = INTENT_KNOWLEDGE
    logger.info(f"[tutor.intent] intent={intent}")
    return {"intent": intent}


async def general_chat(state: dict) -> dict:
    logger.info(f"[tutor.general] project_id={state.get('project_id', '?')} entry")
    llm = get_llm()
    res = await llm.ainvoke(
        [
            SystemMessage(
                content="You are a friendly AI Study Companion. The user is chatting casually "
                "(greeting, asking what you can do, etc.). Reply conversationally and briefly. "
                "Mention you can answer questions grounded in their uploaded project materials, "
                "quiz them, and track their concept mastery."
            ),
            HumanMessage(content=state.get("user_question", "")),
        ]
    )
    logger.info(f"[tutor.general] done")
    return {"final_answer": res.content, "messages": [res]}


def retrieve_context(state: dict) -> dict:
    embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        google_api_key=settings.GOOGLE_API_KEY,
        output_dimensionality=768,
    )
    query_vector = embeddings.embed_query(state["user_question"])
    db = SessionLocal()
    try:
        chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.project_id == uuid.UUID(state["project_id"]))
            .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            .limit(5)
            .all()
        )
        context = [f"[Source: Page {c.page_number}] {c.content}" for c in chunks]
    finally:
        db.close()
    return {"retrieved_context": context}


async def grade_documents(state: dict) -> dict:
    llm = get_llm()
    res = await llm.ainvoke(
        [
            SystemMessage(
                content="You evaluate whether the provided Context is sufficient to answer the user's question. "
                "Output ONLY the word 'yes' or the word 'no'. No other text."
            ),
            HumanMessage(
                content=f"Question: {state['user_question']}\n\nContext:\n"
                + "\n".join(state.get("retrieved_context", []))
            ),
        ]
    )
    return {"sufficient_evidence": res.content.strip().lower() == "yes"}


def reject_answer(state: dict) -> dict:
    return {"final_answer": REJECT_MESSAGE, "messages": [AIMessage(content=REJECT_MESSAGE)]}


async def generate_answer(state: dict) -> dict:
    project_id = state.get("project_id", "?")
    logger.info(f"[tutor.generate] project_id={project_id} start")
    llm = get_llm()
    context = "\n".join(state.get("retrieved_context", []))

    # Silent mastery signal: does the user demonstrate understanding?
    try:
        history_txt = "\n".join(
            f"{m.type}: {m.content[:500]}" for m in (state.get("messages") or [])[-6:]
        )
        sig_res = await llm.ainvoke(
            [
                SystemMessage(
                    content="Does the user demonstrate understanding of any core concepts in this interaction? "
                    "If yes, output ONLY JSON like {\"concept_name\": \"X\", \"confidence_score\": 80}. "
                    "If no, output null. No other text."
                ),
                HumanMessage(
                    content=f"Question: {state.get('user_question')}\nContext:\n{context[:3000]}\nHistory:\n{history_txt}"
                ),
            ]
        )
        raw = sig_res.content.strip().replace("```json", "").replace("```", "").strip()
        if raw and raw.lower() != "null" and raw.lower() != "none":
            try:
                signal = ChatMasterySignal(**json.loads(raw))
                from app.tasks.concept_tasks import update_mastery_from_chat_task

                update_mastery_from_chat_task.delay(
                    str(project_id), signal.concept_name, float(signal.confidence_score)
                )
                logger.info(f"[tutor.generate] mastery signal project={project_id} concept={signal.concept_name}")
            except Exception as pe:
                logger.warning(f"[tutor.generate] mastery parse/dispatch skipped: {pe}")
    except Exception as e:
        logger.warning(f"[tutor.generate] silent eval failed project={project_id}: {e}")

    res = await llm.ainvoke(
        [
            SystemMessage(
                content="You are an AI Study Companion. Answer the user's question using ONLY the provided Context. "
                "If the context does not contain the answer, state 'I cannot answer this based on the provided materials.' "
                "You MUST provide a citation for every factual claim as [Source: Page X]."
                f"\n\nContext:\n{context}"
            ),
            HumanMessage(content=state["user_question"]),
        ]
    )
    logger.info(f"[tutor.generate] project_id={project_id} done")
    return {"final_answer": res.content, "messages": [res]}
