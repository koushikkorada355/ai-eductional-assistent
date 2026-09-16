from typing import TypedDict, List, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class TutorState(TypedDict):
    user_question: str
    project_id: str
    messages: Annotated[List[BaseMessage], add_messages]
    retrieved_context: List[str]
    retrieved_sources: List[dict]
    sufficient_evidence: bool
    final_answer: str
    citations: List[dict]
    intent: str
