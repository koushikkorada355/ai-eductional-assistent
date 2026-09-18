"""Background learning-context maintenance. All tasks are best-effort:
they never raise into the tutor response path."""
from collections import defaultdict
from datetime import datetime
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage

from app.db.session import SessionLocal
import app.db.base  # noqa: F401
from app.db.models.assessment import Concept
from app.db.models.chat import ChatSession, Message
from app.db.models.learning import ConversationSummary
from app.db.models.mastery import QuizHistory
from app.db.models.project import Project
from app.db.models.space import Space
from app.ai.llm import get_llm
from app.services.learning_service import (
    RECENT_MESSAGE_COUNT,
    concept_vocabulary, extract_user_name, ground_candidate,
    is_noise_message, parse_extraction, should_summarize, upsert_memory,
)
from app.tasks.celery_app import celery_app
from app.services.ai_usage_service import track_ai_call


def _owner(db, project_id):
    project = db.get(Project, project_id)
    space = db.get(Space, project.space_id) if project else None
    return (space.user_id if space else None), project


@celery_app.task(name="learning.summarize_conversation")
@track_ai_call("summarization")
def summarize_conversation_task(chat_session_id: str) -> str:
    db = SessionLocal()
    try:
        import uuid as _uuid

        session = db.get(ChatSession, _uuid.UUID(chat_session_id))
        if session is None:
            return "skipped:no-session"
        messages = (
            db.query(Message)
            .filter(Message.chat_session_id == session.id)
            .order_by(Message.created_at)
            .all()
        )
        row = (
            db.query(ConversationSummary)
            .filter(ConversationSummary.chat_session_id == session.id)
            .first()
        )
        if row and row.last_message_id:
            new_since = sum(1 for m in messages if m.created_at and row.updated_at and m.created_at > row.updated_at)
        else:
            new_since = len(messages)
        if not should_summarize(len(messages), new_since):
            return "skipped:too-short"
        # Compress everything except the recent verbatim tail. Noise first:
        # greetings, small-talk, and drill placeholder bubbles carry no study
        # content and must never enter the summary.
        older = messages[: max(0, len(messages) - RECENT_MESSAGE_COUNT)]
        if not older:
            return "skipped:too-short"
        kept = [m for m in older[-30:] if not is_noise_message(m.content or "")]
        if not kept:
            return "skipped:nothing-material"
        transcript = "\n".join(
            f"{m.role}: {(m.content or '')[:500]}" for m in kept
        )
        concept_names = [c.name for c in
                         db.query(Concept).filter(Concept.project_id == session.project_id).all()][:30]
        llm = get_llm()
        res = llm.invoke([
            SystemMessage(content=(
                "Summarize this tutoring conversation for continuity in 4-8 sentences. "
                "Preserve: current learning topic, concepts discussed, the learner's "
                "misunderstandings, explanations already given, unresolved questions. "
                "Summarize ONLY content about the learner's study materials"
                + (f" (known material topics: {', '.join(concept_names)})" if concept_names else "")
                + ". Never preserve off-topic or unrelated questions. "
                "Drop greetings, thanks, and repetition."
                + (f"\n\nPrevious summary to update:\n{row.summary}" if row else "")
            )),
            HumanMessage(content=transcript[:8000]),
        ])
        summary = (res.content or "").strip()
        if not summary:
            return "skipped:empty-summary"
        if row:
            row.summary = summary
            row.last_message_id = older[-1].id
            row.updated_at = datetime.utcnow()
        else:
            db.add(ConversationSummary(
                chat_session_id=session.id, summary=summary,
                last_message_id=older[-1].id,
            ))
        db.commit()
        return "summarized"
    except Exception as e:
        db.rollback()
        logger.warning(f"[learning.summarize] failed session={chat_session_id}: {e}")
        return f"failed:{e}"
    finally:
        db.close()


@celery_app.task(name="learning.extract_context")
@track_ai_call("summarization")
def extract_learning_context_task(chat_session_id: str, user_message_id: str) -> str:
    db = SessionLocal()
    try:
        import uuid as _uuid

        session = db.get(ChatSession, _uuid.UUID(chat_session_id))
        if session is None:
            return "skipped:no-session"
        user_id, project = _owner(db, session.project_id)
        if user_id is None or project is None:
            return "skipped:no-owner"
        try:
            user_msg = db.get(Message, _uuid.UUID(user_message_id))
        except ValueError:
            return "skipped:bad-id"
        if user_msg is None or user_msg.role != "user":
            return "skipped:no-message"
        # Small-talk and drill placeholder bubbles carry no study content:
        # skip extraction entirely (also saves the LLM call).
        if is_noise_message(user_msg.content or ""):
            return "skipped:small-talk"
        assistant_msg = (
            db.query(Message)
            .filter(Message.chat_session_id == session.id,
                    Message.role == "assistant",
                    Message.created_at >= user_msg.created_at)
            .order_by(Message.created_at)
            .first()
        )
        exchange = f"User: {(user_msg.content or '')[:1000]}"
        if assistant_msg:
            exchange += f"\nAssistant: {(assistant_msg.content or '')[:1000]}"
        # Synchronous-safe fast path: persist a self-introduced name
        # deterministically (no LLM needed). The LLM extractor below is
        # explicitly told to keep names too, as a second chance.
        results = []
        introduced = extract_user_name(user_msg.content or "")
        if introduced:
            results.append(upsert_memory(
                db, user_id=user_id, project_id=project.id,
                type="user_fact", concept_id=None,
                content=f"User's name is {introduced}",
                confidence=0.95, source="conversation",
                source_id=user_msg.id,
            ))
        llm = get_llm()
        known_topics = [c.name for c in db.query(Concept).filter(Concept.project_id == project.id).all()][:30]
        res = llm.invoke([
            SystemMessage(content=(
                "Extract durable learner context from this tutoring exchange. "
                "Return ONLY a JSON list like "
                '[{"type": "weakness", "concept_name": "recursion", "content": "...", "confidence": 0.8}] '
                "or null when nothing is worth persisting. Allowed types: goal, preference, "
                "strength, weakness, repeated_mistake, tutor_context, user_fact. "
                "Only extract content about the learner's study materials"
                + (f" (known material topics: {', '.join(known_topics)})" if known_topics else "")
                + ". Never persist unrelated or off-topic questions or topics. "
                "Rules: persist goals, learning preferences, evident strengths/weaknesses, "
                "repeated mistakes, AND the user's name (type user_fact, content like "
                "\"User's name is X\") whenever they introduce themselves. "
                "IGNORE greetings, thanks, small talk, and one-off questions. "
                "NEVER infer a weakness from a single wrong answer. "
                "Never store assistant assumptions as learner facts. Keep content under 200 chars."
            )),
            HumanMessage(content=exchange),
        ])
        candidates = parse_extraction(res.content)
        concepts = db.query(Concept).filter(Concept.project_id == project.id).all()
        by_name = {c.name.lower(): c for c in concepts}
        vocab = concept_vocabulary([c.name for c in concepts])

        for cand in candidates:
            # Gate everything but names: each row must tie to the materials.
            if cand["type"] != "user_fact":
                concept_id, keep = ground_candidate(
                    cand["concept_name"], cand["content"], by_name, vocab)
                if not keep:
                    logger.info(
                        "[learning.extract] dropped ungrounded "
                        f"{cand['type']}: {(cand['content'] or '')[:60]}")
                    continue
            else:
                concept_id = None
                if cand["concept_name"]:
                    exact = by_name.get(cand["concept_name"].lower())
                    if exact:
                        concept_id = exact.id
            results.append(upsert_memory(
                db, user_id=user_id, project_id=project.id,
                type=cand["type"], concept_id=concept_id,
                content=cand["content"], confidence=cand["confidence"],
                source="conversation", source_id=user_msg.id,
            ))
        # Repeated mistakes from real assessment data (>=2 incorrect, same concept).
        concept_ids = [c.id for c in concepts]
        if concept_ids:
            hist = (
                db.query(QuizHistory)
                .filter(QuizHistory.user_id == user_id,
                        QuizHistory.concept_id.in_(concept_ids),
                        QuizHistory.is_correct.is_(False))
                .all()
            )
            counts = defaultdict(int)
            for h in hist:
                counts[h.concept_id] += 1
            names = {c.id: c.name for c in concepts}
            for cid, n in counts.items():
                if n >= 2:
                    results.append(upsert_memory(
                        db, user_id=user_id, project_id=project.id,
                        type="repeated_mistake", concept_id=cid,
                        content=f"Repeated mistakes on {names.get(cid, 'this concept')} ({n} incorrect answers)",
                        confidence=0.85, source="assessment", source_id=None,
                    ))
        return f"done:{','.join(results) or 'nothing-useful'}"
    except Exception as e:
        db.rollback()
        logger.warning(f"[learning.extract] failed session={chat_session_id}: {e}")
        return f"failed:{e}"
    finally:
        db.close()
