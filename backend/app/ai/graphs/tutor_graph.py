from langgraph.graph import StateGraph, START, END
from app.ai.state import TutorState
from app.ai.nodes import (
    detect_intent,
    general_chat,
    retrieve_context,
    retrieve_learning_context,
    grade_documents,
    reject_answer,
    generate_answer,
    INTENT_GENERAL,
)
from app.db.checkpointer import checkpointer


def route_intent(state: dict) -> str:
    return "general_chat" if state.get("intent") == INTENT_GENERAL else "retrieve_context"


def route_evidence(state: dict) -> str:
    return "generate_answer" if state.get("sufficient_evidence") else "reject_answer"


workflow = StateGraph(TutorState)
workflow.add_node("detect_intent", detect_intent)
workflow.add_node("general_chat", general_chat)
workflow.add_node("retrieve_context", retrieve_context)
workflow.add_node("retrieve_learning_context", retrieve_learning_context)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("generate_answer", generate_answer)
workflow.add_node("reject_answer", reject_answer)
# Path A (general) bypasses RAG; Path B (knowledge) runs the strict RAG pipeline
workflow.add_edge(START, "detect_intent")
workflow.add_conditional_edges("detect_intent", route_intent)
workflow.add_edge("general_chat", END)
workflow.add_edge("retrieve_context", "retrieve_learning_context")
workflow.add_edge("retrieve_learning_context", "grade_documents")
workflow.add_conditional_edges("grade_documents", route_evidence)
workflow.add_edge("generate_answer", END)
workflow.add_edge("reject_answer", END)

tutor_app = workflow.compile(checkpointer=checkpointer)
