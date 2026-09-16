from typing import TypedDict, List, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class TutorState(TypedDict):
    user_question: str
    project_id: str
    messages: Annotated[List[BaseMessage], add_messages]
    retrieved_context: List[str]
    sufficient_evidence: bool
    final_answer: str
    intent: str


class QuizState(TypedDict):
    project_id: str
    quiz_id: str
    messages: Annotated[List[BaseMessage], add_messages]
    current_question: str
    current_question_id: str
    question_type: str
    user_answer: str
    evaluation: dict
    concepts_to_test: List[str]
    selected_concept: str
    selected_concept_id: str
    questions_asked: int
    error: str
