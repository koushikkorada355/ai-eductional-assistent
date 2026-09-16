from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.ai.state.assignment_state import AssignmentState
from app.ai.nodes.assignment_nodes import (
    generate_assignment_questions,
    grade_assignment_submission,
    assignment_error,
    route_entry,
)


def route_after_generate(state: dict) -> str:
    return "assignment_error" if state.get("error") else "end"


def route_after_grade(state: dict) -> str:
    return "assignment_error" if state.get("error") else "end"


graph_builder = StateGraph(AssignmentState)

graph_builder.add_node("generate_questions", generate_assignment_questions)
graph_builder.add_node("grade_submission", grade_assignment_submission)
graph_builder.add_node("assignment_error", assignment_error)

graph_builder.add_conditional_edges(
    START,
    route_entry,
    {"generate_questions": "generate_questions", "grade_submission": "grade_submission"},
)
graph_builder.add_conditional_edges(
    "generate_questions", route_after_generate, {"assignment_error": "assignment_error", "end": END}
)
graph_builder.add_conditional_edges(
    "grade_submission", route_after_grade, {"assignment_error": "assignment_error", "end": END}
)
graph_builder.add_edge("assignment_error", END)

assignment_app = graph_builder.compile(checkpointer=MemorySaver())
