import uuid
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.config import settings
from app.db.session import SessionLocal
from app.db.models.document import DocumentChunk
from app.ai.llm import get_llm

REJECT_MESSAGE = "I cannot answer this based on the provided materials."


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
    llm = get_llm()
    context = "\n".join(state.get("retrieved_context", []))
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
    return {"final_answer": res.content, "messages": [res]}
