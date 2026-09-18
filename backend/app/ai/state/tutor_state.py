from typing import TypedDict, List, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class TutorState(TypedDict):
    user_question: str
    project_id: str
    user_id: str
    chat_session_id: str
    messages: Annotated[List[BaseMessage], add_messages]
    retrieved_context: List[str]
    retrieved_sources: List[dict]
    sufficient_evidence: bool
    final_answer: str
    citations: List[dict]
    intent: str
    # Follow-up questions shown as clickable chips under the AI response.
    suggested_questions: List[str]
    # Quick-action directive (see app.ai.actions): prompt-shaping hint for
    # generate_answer only. Retrieval always runs on user_question.
    action_hint: str
    # Raw quick-action id (e.g. "practice") so nodes can branch on behaviour
    # — practice turns must never emit mastery signals. Empty when none.
    action_id: str
    # Rolling compression of older in-window turns (high-priority bullets
    # only), written by the compress_history node to keep prompts small on
    # long threads. Empty when the window already fits the budget.
    history_summary: str
    # Persistent learning context (never overrides document evidence).
    conversation_summary: str
    relevant_learning_context: List[str]
    relevant_assessment_context: str
    user_name: str
