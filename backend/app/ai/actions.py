"""AI Tutor Quick Actions — action abstraction over the existing pipeline.

Exactly four actions. Each reuses the SAME retrieval (RAG), the SAME
LangGraph workflow, and the SAME LLM. Only the prompt-shaping directive
differs per action; common context handling lives in _run_tutor_turn.

GENERATE_QUIZ is intentionally absent here: it reuses the existing quiz
system end-to-end (frontend dispatches the normal quiz-start flow), so no
tutor-turn directive is needed for it.
"""
import re
from typing import Optional

SUMMARIZE = "summarize"
DEEP_DIVE = "deep_dive"
CREATE_FLASHCARDS = "create_flashcards"

VALID_ACTIONS = (SUMMARIZE, DEEP_DIVE, CREATE_FLASHCARDS)

# Prompt-shaping directives appended (LLM-side only, never stored) to the
# tutor turn. Retrieval still runs on the user's own question text.
ACTION_DIRECTIVES = {
    SUMMARIZE: (
        "The user triggered the 'Summarize' quick action. Produce a concise "
        "summary of the relevant Context: lead with 2-4 bullet key points, "
        "then at most one short paragraph. Omit secondary detail. Stay "
        "strictly within the provided Context."
    ),
    DEEP_DIVE: (
        "The user triggered the 'Deep Dive' quick action. Go deep on the "
        "topic using the provided Context: cover important details, how the "
        "parts relate to each other, and concrete examples where useful. "
        "Organize with ##/### headings. Stay strictly within the provided "
        "Context; if the Context runs out, say what is missing instead of "
        "speculating."
    ),
    CREATE_FLASHCARDS: (
        "The user triggered the 'Create Flashcards' quick action. Distill the "
        "relevant Context into 4-8 study flashcards. Output ONLY flashcard "
        "blocks in exactly this format, one after another, no intro/outro:\n"
        "Q: <single focused question>\n"
        "A: <concise answer, 1-3 sentences>\n"
        "Stay strictly within the provided Context."
    ),
}


def get_action_hint(action: Optional[str]) -> str:
    """Return the LLM-side directive for an action ('' when none/invalid)."""
    if not action:
        return ""
    return ACTION_DIRECTIVES.get(action, "")


_QA_RE = re.compile(
    r"Q:\s*(?P<q>.+?)\s*\nA:\s*(?P<a>.+?)(?=\nQ:|\Z)", re.DOTALL,
)
MAX_FLASHCARDS = 10


def parse_flashcards(answer: str) -> list:
    """Extract [{question, answer}] pairs from a flashcards-format reply."""
    cards = []
    for m in _QA_RE.finditer(answer or ""):
        q = " ".join(m.group("q").split())
        a = " ".join(m.group("a").split())
        if q and a:
            cards.append({"question": q[:300], "answer": a[:600]})
        if len(cards) >= MAX_FLASHCARDS:
            break
    return cards
