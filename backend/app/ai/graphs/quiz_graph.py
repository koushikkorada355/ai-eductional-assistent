from langgraph.graph import StateGraph, START, END
from app.ai.state import QuizState
from app.ai.nodes import (
    assess_mastery,
    generate_question,
    evaluate_answer,
    update_mastery,
    quiz_error,
    route_after_assess,
    route_loop,
)
from app.db.checkpointer import checkpointer

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
