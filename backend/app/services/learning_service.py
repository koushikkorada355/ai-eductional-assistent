"""Persistent learning context: relevance, parsing, and storage helpers.

Two memories stay separate:
- Conversation memory = full Message rows + a rolling ConversationSummary
  of older messages (recent messages always kept verbatim).
- Learning memory = LearningContext rows (goals, preferences, strengths,
  weaknesses, repeated mistakes). Only relevant rows reach the LLM.
"""
import json
import re
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.db.models.learning import (
    ALLOWED_TYPES, ConversationSummary, LearningContext,
    TYPE_GOAL, TYPE_PREFERENCE, TYPE_USER_FACT,
)

# Summarize when a session reaches this many messages...
SUMMARY_MESSAGE_THRESHOLD = 20
# ...and at least this many new messages arrived since the last summary.
SUMMARY_NEW_MESSAGE_GAP = 10
# Recent messages passed verbatim to the LLM (older ones may be summarized).
RECENT_MESSAGE_COUNT = 10
# Always-retrieved memory types (high value, tiny volume), most recent first.
ALWAYS_TYPES = (TYPE_GOAL, TYPE_PREFERENCE, TYPE_USER_FACT)
ALWAYS_TYPE_CAP = 3
# Max rows / chars injected into any single prompt section.
MAX_MEMORY_ROWS = 6
MAX_SECTION_CHARS = 1500


def significant_words(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) >= 5}


def concept_matches(question, concept_name):
    """Conservative relevance: full-name substring or >=2 significant words."""
    q = (question or "").lower()
    name = (concept_name or "").lower().strip()
    if not name or len(name) < 3:
        return False
    if name in q:
        return True
    name_words = significant_words(name)
    if len(name_words) < 2:
        return False
    return len(name_words & significant_words(q)) >= 2


# Greetings / small-talk only (hii, thanks, ok …). Anchored full-match so
# real (even short) questions always pass through. Mirrors the frontend
# guard in QuickActions.jsx.
SMALL_TALK_RE = re.compile(
    r"^(h+i+|hello+|hey+|yo|sup|thanks?|thank\s*you|thx|bye+|"
    r"good\s?(morning|afternoon|evening|night)|o+k+|okay+|sure|yes+|no+|"
    r"please+|help+|test+(ing)?|how\s+are\s+you(\s+doing)?)\W*$",
    re.IGNORECASE,
)

# Drill placeholder bubbles ("Generating practice questions…", …) carry no
# topic. Frontend source of truth is QuickActions.jsx; this matches the
# whole family so backend filtering never depends on exact strings.
PLACEHOLDER_RE = re.compile(r"^generating\s+.+\u2026\s*$", re.IGNORECASE)


def is_small_talk(text):
    """True for greeting/small-talk-only messages (never study content)."""
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if not t:
        return True
    return bool(SMALL_TALK_RE.match(t))


def is_placeholder_bubble(text):
    """True for drill status bubbles ("Generating…") — no topic inside."""
    return bool(PLACEHOLDER_RE.match(re.sub(r"\s+", " ", str(text or "")).strip()))


def is_noise_message(text):
    """True for messages that must never enter memory, summaries, or drills:
    small-talk and drill placeholder bubbles."""
    return is_small_talk(text) or is_placeholder_bubble(text)


def concept_vocabulary(concept_names):
    """Significant-word set across project concept names (grounding gate)."""
    vocab = set()
    for n in concept_names or []:
        vocab |= significant_words(n)
    return vocab


def ground_candidate(cand_name, content, by_name, vocab):
    """Decide whether an extracted memory row may be stored.

    Gate-everything-but-names rule: a row is kept only if it names a real
    project concept (case-insensitive exact match) or shares >=2
    significant words with project concept vocabulary. Returns
    (concept_id_or_None, keep_bool). Callers must exempt user_fact name
    rows before calling.
    """
    if cand_name:
        exact = (by_name or {}).get(cand_name.lower())
        if exact is not None:
            return exact.id, True
        return None, False
    if len(significant_words(content) & (vocab or set())) >= 2:
        return None, True
    return None, False


def should_summarize(total_messages, new_since_summary):
    """Pure trigger: big enough conversation with enough unsummarized tail."""
    if total_messages < SUMMARY_MESSAGE_THRESHOLD:
        return False
    return new_since_summary >= SUMMARY_NEW_MESSAGE_GAP


def parse_extraction(raw):
    """Parse the extractor LLM output into validated memory candidates.

    Returns [{type, concept_name|None, content, confidence}]. Anything
    malformed, out-of-vocabulary, or empty yields [] (conservative: store
    nothing rather than garbage).
    """
    if not raw:
        return []
    text = str(raw).strip().replace("```json", "").replace("```", "").strip()
    if not text or text.lower() in ("null", "none", "[]"):
        return []
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        t = it.get("type")
        content = str(it.get("content") or "").strip()
        if t not in ALLOWED_TYPES or not (3 <= len(content) <= 500):
            continue
        try:
            conf = float(it.get("confidence", 0.7))
        except (TypeError, ValueError):
            conf = 0.7
        concept_name = it.get("concept_name")
        concept_name = str(concept_name).strip()[:200] if concept_name else None
        out.append({"type": t, "concept_name": concept_name,
                    "content": content, "confidence": max(0.0, min(1.0, conf))})
    return out


TYPE_LABELS = {
    "goal": "Goal",
    "preference": "Preference",
    "strength": "Strength",
    "weakness": "Weakness",
    "repeated_mistake": "Repeated mistake",
    "tutor_context": "Context",
    "user_fact": "User fact",
}


def extract_user_name(text):
    """Extract a self-introduced first name from free text.

    Matches "my name is X", "i am X", "i'm X", "call me X".
    Returns the capitalized name or None. Conservative: single
    alphabetic token, 2-30 chars, not a stopword.
    """
    if not text:
        return None
    lowered = re.sub(r"\s+", " ", str(text)).strip()
    m = re.search(
        r"(?:my name is|call me|i am|i'm|i’m)\s+([A-Za-z][A-Za-z'\-]{1,29})",
        lowered,
        re.IGNORECASE,
    )
    if not m:
        return None
    name = m.group(1).strip().strip("'\".,!?")
    stop = {"a", "an", "the", "here", "there", "someone", "nobody",
            "student", "learner", "user", "human", "tutor", "ai",
            "happy", "glad", "sorry", "fine", "good", "ok", "okay",
            "asking", "wondering", "trying", "looking", "confused",
            "stuck", "lost", "new", "back"}
    if name.lower() in stop or len(name) < 2:
        return None
    return name[:30].capitalize()


def is_name_question(text):
    """True when the user asks the tutor for their own stored name."""
    if not text:
        return False
    t = str(text).lower()
    return bool(re.search(r"\bmy name\b", t)) and bool(
        re.search(r"\b(what|who|do you know|remember|recall|tell me)\b", t)
    )


def user_name_from_rows(rows):
    """Return the most recently updated stored user name, or None."""
    cands = [r for r in (rows or []) if getattr(r, "type", "") == "user_fact"]
    if not cands:
        return None
    cands.sort(key=lambda r: getattr(r, "updated_at", None) or getattr(r, "created_at", None) or datetime.min, reverse=True)
    for r in cands:
        content = (getattr(r, "content", "") or "").strip()
        m = re.search(r"name is ([A-Za-z][A-Za-z'\-]{1,29})", content)
        if m:
            return m.group(1).capitalize()
        if 1 <= len(content.split()) <= 3 and re.fullmatch(r"[A-Za-z'\- ]{2,40}", content):
            # content stored as bare name
            return content.split()[0].capitalize()
    return None


def render_memory_lines(rows, concept_names):
    """Render memory rows as short labeled lines for the prompt."""
    lines = []
    for r in rows[:MAX_MEMORY_ROWS]:
        label = TYPE_LABELS.get(r.type, r.type)
        if r.concept_id and r.concept_id in concept_names:
            label += f" ({concept_names[r.concept_id]})"
        lines.append(f"{label}: {r.content}")
    text = "\n".join(lines)
    return text[:MAX_SECTION_CHARS]


def format_assessment(stats):
    """stats: [{concept, correct, total, last_mistake|None}] -> prompt lines."""
    lines = []
    for s in stats:
        line = f"{s['concept']}: {s['correct']}/{s['total']} correct recently"
        if s.get("last_mistake"):
            line += f"; common mistake: {s['last_mistake'][:160]}"
        lines.append(line)
    text = "\n".join(lines)
    return text[:MAX_SECTION_CHARS]


def get_summary(db, chat_session_id):
    row = (
        db.query(ConversationSummary)
        .filter(ConversationSummary.chat_session_id == chat_session_id)
        .first()
    )
    if not row:
        return None, None
    return row.summary, row.last_message_id


def upsert_memory(db, *, user_id, project_id, type, concept_id, content,
                  confidence=0.7, source="system", source_id=None):
    """Create or update a memory row. Retries of the same event converge
    to one row: concept-linked rows match (project, type, concept); event
    rows match (project, type, source, source_id); unique indexes backstop.
    Returns 'created' | 'updated' | 'duplicate'."""
    if type not in ALLOWED_TYPES or not content:
        return "skipped:invalid"
    existing = None
    if concept_id is not None:
        existing = (
            db.query(LearningContext)
            .filter(LearningContext.project_id == project_id,
                    LearningContext.type == type,
                    LearningContext.concept_id == concept_id)
            .first()
        )
    elif source_id is not None:
        existing = (
            db.query(LearningContext)
            .filter(LearningContext.project_id == project_id,
                    LearningContext.type == type,
                    LearningContext.source == source,
                    LearningContext.source_id == source_id)
            .first()
        )
    try:
        if existing:
            existing.content = content
            existing.confidence = confidence
            existing.updated_at = datetime.utcnow()
            db.commit()
            return "updated"
        db.add(LearningContext(
            user_id=user_id, project_id=project_id, type=type,
            concept_id=concept_id, content=content[:500],
            confidence=confidence, source=source, source_id=source_id,
        ))
        db.commit()
        return "created"
    except IntegrityError:
        db.rollback()
        return "duplicate:already-stored"
    except Exception:
        db.rollback()
        return "skipped:error"
