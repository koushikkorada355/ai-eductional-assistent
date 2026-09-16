from langgraph.graph import StateGraph, START, END
from app.ai.state import TutorState
from app.ai.nodes import retrieve_context, grade_documents, reject_answer, generate_answer
from app.db.checkpointer import checkpointer


def route_evidence(state: dict) -> str:
    return "generate_answer" if state.get("sufficient_evidence") else "reject_answer"


workflow = StateGraph(TutorState)
workflow.add_node("retrieve_context", retrieve_context)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("generate_answer", generate_answer)
workflow.add_node("reject_answer", reject_answer)
workflow.add_edge(START, "retrieve_context")
workflow.add_edge("retrieve_context", "grade_documents")
workflow.add_conditional_edges("grade_documents", route_evidence)
workflow.add_edge("generate_answer", END)
workflow.add_edge("reject_answer", END)

tutor_app = workflow.compile(checkpointer=checkpointer)
