"""AI Tutor Quick Actions — action abstraction over the existing pipeline.

Exactly five actions. Each reuses the SAME retrieval (RAG), the SAME
LangGraph workflow, and the SAME LLM. Only the prompt-shaping directive
differs per action; common context handling lives in _run_tutor_turn.

GENERATE_QUIZ is intentionally absent here: it reuses the existing quiz
system end-to-end (frontend dispatches the normal quiz-start flow), so no
tutor-turn directive is needed for it.

PRACTICE is chat-only by design: the turn renders as interactive MCQs in
the conversation, writes nothing to quiz tables, and never emits a mastery
signal — it cannot move mastery in either direction.
"""
import re
from typing import Optional

SUMMARIZE = "summarize"
DEEP_DIVE = "deep_dive"
CREATE_FLASHCARDS = "create_flashcards"
PRACTICE = "practice"

VALID_ACTIONS = (SUMMARIZE, DEEP_DIVE, CREATE_FLASHCARDS, PRACTICE)

# Actions whose source is the conversation itself rather than retrieved
# documents: they skip the intent classifier and the evidence gate, and
# their user message is a topic-free placeholder bubble.
CONVERSATION_ACTIONS = (SUMMARIZE, DEEP_DIVE, PRACTICE)

# Prompt-shaping directives appended (LLM-side only, never stored) to the
# tutor turn. Retrieval still runs on the user's own question text.
ACTION_DIRECTIVES = {
    SUMMARIZE: (
        "The user triggered the 'Summarize' quick action. Summarize what has "
        "been discussed in THIS conversation: lead with 2-4 bullet key points "
        "capturing the important topics, definitions, and conclusions from the "
        "message history and its summaries, then at most one short paragraph. "
        "Base it on the conversation (message history + provided summaries); "
        "use the retrieved Context only to verify facts. Omit greetings, "
        "small-talk, repetition, and placeholder/status messages. If the "
        "conversation history is empty, summarize the retrieved Context instead."
    ),
    DEEP_DIVE: (
        "The user triggered the 'Deep Dive' quick action. Go deep on the "
        "topics discussed in THIS conversation: cover important details, how "
        "the parts relate to each other, and concrete examples where useful. "
        "Base it on the conversation (message history + provided summaries); "
        "use the retrieved Context to ground facts and fill gaps. Organize "
        "with ##/### headings. Omit greetings, small-talk, and repetition; "
        "if the history is thin, say what is missing instead of speculating."
    ),
    CREATE_FLASHCARDS: (
        "The user triggered the 'Create Flashcards' quick action. Distill the "
        "relevant Context into 4-8 study flashcards. Output ONLY flashcard "
        "blocks in exactly this format, one after another, no intro/outro:\n"
        "Q: <single focused question>\n"
        "A: <concise answer, 1-3 sentences>\n"
        "Stay strictly within the provided Context."
    ),
    PRACTICE: (
        "The user triggered the 'Practice' quick action. Create exactly 3 "
        "multiple-choice practice questions based STRICTLY on the topics "
        "discussed in the recent conversation history (the message history). "
        "Do NOT use the retrieved Context unless the conversation history is "
        "empty — only then base the questions on the most important concepts "
        "from the Context. "
        "Ignore greetings, small-talk, placeholder/status messages, and any "
        "off-topic or unrelated questions in the history — base MCQs only on "
        "material-related discussion. If the history holds no "
        "material-related discussion and the Context is thin, say so instead "
        "of inventing questions. "
        "Output ONLY MCQ blocks in exactly this format, one after another, "
        "no intro, no outro, no citations:\n"
        "Q: <single focused question>\n"
        "A) <option>\nB) <option>\nC) <option>\nD) <option>\n"
        "Answer: <single letter A-D>\n"
        "Why: <one-line explanation of why the correct answer is right>\n"
        "Exactly 4 options per question. Exactly 3 questions."
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


MAX_PRACTICE_MCQ = 5

_MCQ_OPTION_RE = re.compile(r"^\s*([A-Da-d])\s*[).:}\-–—]\s*(.+?)\s*$")
_MCQ_ANSWER_RE = re.compile(r"^\s*Answer\s*:\s*([A-Da-d])\b")
_MCQ_WHY_RE = re.compile(r"^\s*(?:Why|Explanation)\s*:\s*(.+?)\s*$")


def parse_practice_mcq(answer: str) -> list:
    """Extract [{question, options[4], answer_index, explanation}] from a
    practice-format reply. Tolerant of option-marker drift (A) / A. / A:),
    case, and a missing Why line. Blocks without 4 options + a valid answer
    letter are dropped so the UI never renders a broken question."""
    cards = []
    # Split into Q:-led blocks; the first chunk (intro) is discarded.
    blocks = re.split(r"(?m)^\s*Q\s*:\s*", answer or "")
    for block in blocks[1:]:
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if not lines:
            continue
        question = " ".join(lines[0].split())
        options: list = []
        answer_index: int | None = None
        explanation = ""
        for ln in lines[1:]:
            m_opt = _MCQ_OPTION_RE.match(ln)
            if m_opt and len(options) < 4:
                options.append(" ".join(m_opt.group(2).split()))
                continue
            m_ans = _MCQ_ANSWER_RE.match(ln)
            if m_ans:
                answer_index = ord(m_ans.group(1).upper()) - ord("A")
                continue
            m_why = _MCQ_WHY_RE.match(ln)
            if m_why:
                explanation = " ".join(m_why.group(1).split())
        if not question or len(options) != 4:
            continue
        if answer_index is None or not 0 <= answer_index <= 3:
            continue
        cards.append({"question": question[:300],
                      "options": [o[:300] for o in options],
                      "answer_index": answer_index,
                      "explanation": explanation[:600]})
        if len(cards) >= MAX_PRACTICE_MCQ:
            break
    return cards
