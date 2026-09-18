import json
import re
import uuid
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.config import settings
from app.db.session import SessionLocal
from app.db.models.document import DocumentChunk, Document
from app.ai.llm import get_llm
from app.schemas.quiz import ChatMasterySignal
from app.services.learning_service import RECENT_MESSAGE_COUNT

REJECT_MESSAGE = (
    "That's outside what your uploaded materials cover right now — "
    "try asking about one of your project topics, and I'll explore it with you."
)

INTENT_GENERAL = "general"
INTENT_KNOWLEDGE = "knowledge"


def _get_suggest_llm():
    """Low-temperature LLM for focused, deterministic follow-up questions."""
    try:
        from langchain_openai import ChatOpenAI
        from app.config import settings
        from app.services.ai_usage_service import TrackedLLM
        if settings.INCEPTION_API_KEY:
            return TrackedLLM(ChatOpenAI(
                model=settings.INCEPTION_MODEL or "mercury-2.5", temperature=0.2,
                api_key=settings.INCEPTION_API_KEY,
                base_url=settings.INCEPTION_BASE_URL or "https://api.inceptionlabs.ai/v1",
            ))
        # Groq fallback (disabled 2026-09-18, kept for easy switch-back):
        # from langchain_groq import ChatGroq
        # if settings.GROQ_API_KEY:
        #     return TrackedLLM(ChatGroq(
        #         model=settings.GROQ_MODEL, temperature=0.2,
        #         groq_api_key=settings.GROQ_API_KEY,
        #     ))
    except Exception as e:
        logger.warning(f"[tutor.suggest] low-temp llm fallback: {e}")
    return get_llm()


_VAGUE_PATTERNS = [
    "tell me more", "what else", "what's next", "what is next",
    "next step after", "summarize everything", "give me more",
    "what about", "anything else",
]


def _is_vague(s: str) -> bool:
    low = s.lower()
    return any(p in low for p in _VAGUE_PATTERNS)


def _jaccard(a: str, b: str) -> float:
    ta = {w for w in re.findall(r"[a-z0-9]+", a.lower()) if len(w) >= 4}
    tb = {w for w in re.findall(r"[a-z0-9]+", b.lower()) if len(w) >= 4}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _get_project_concepts(project_id_str: str) -> list:
    """Fetch concept names for a project. Failure-safe — returns [] on any error."""
    try:
        import uuid as _uuid
        from app.db.models.assessment import Concept
        db = SessionLocal()
        try:
            rows = (
                db.query(Concept)
                .filter(Concept.project_id == _uuid.UUID(str(project_id_str)))
                .order_by(Concept.created_at)
                .limit(30)
                .all()
            )
            return [r.name for r in rows if (r.name or "").strip()]
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"[tutor.suggest] concepts lookup skipped: {e}")
        return []


async def _suggest_followups(
    question: str,
    answer: str,
    context_snippet: str = "",
    project_id: str = "",
    conversation_summary: str = "",
    learning_lines: list | None = None,
) -> list:
    """Generate up to 3 follow-ups STRICTLY from conversations + concepts only.

    Sources allowed (and nothing else):
    - Concepts: topic names extracted from the learner's own materials.
    - Conversation: summary of older turns + recent learner context lines.
    Never uses raw retrieved chunks, so suggestions stay inside what the
    learner has actually discussed / what concepts exist.
    Failure-safe — returns [] on any error or when sources are empty.
    """
    try:
        q = (question or "").strip()
        a = (answer or "").strip()
        if not q or not a or a == REJECT_MESSAGE:
            return []
        concepts = _get_project_concepts(project_id) if project_id else []
        summary = (conversation_summary or "").strip()
        lines = [str(x).strip() for x in (learning_lines or []) if str(x).strip()]
        if not concepts and not summary and not lines:
            return []
        concepts_txt = ", ".join(concepts[:30]) if concepts else "None yet"
        convo_txt = ""
        if summary:
            convo_txt += f"Conversation summary:\n{summary[:1500]}\n"
        if lines:
            convo_txt += f"Recent learner context:\n" + "\n".join(lines[:8])[:1500]
        if not convo_txt.strip():
            convo_txt = "No conversation history yet."
        llm = _get_suggest_llm()
        res = await llm.ainvoke(
            [
                SystemMessage(
                    content="You are a study coach writing follow-up questions a learner taps to keep learning. "
                    "STRICT SCOPE: use ONLY the Concepts list and the Conversation below. "
                    "Never invent topics outside them, never use outside knowledge or raw document text.\n"
                    "Write at most 3 follow-up questions.\n"
                    "STRICT RULES:\n"
                    "1) SOURCED: each question must be about one named Concept from the list, or a topic explicitly mentioned in the Conversation. Reuse their exact terms.\n"
                    "2) NOVEL: do NOT paraphrase the user's question. Each question must open a Concept or conversation thread the tutor's answer did not fully cover.\n"
                    "3) DIVERSE ANGLES — make the 3 questions feel different:\n"
                    "   (a) one HOW/WHY mechanism question (how it works, why it matters),\n"
                    "   (b) one EXAMPLE/APPLICATION question (concrete example, use case, what happens when X),\n"
                    "   (c) one COMPARE/EDGE question (difference vs Y, failure case, trade-off, best practice).\n"
                    "   Never start 2 questions with the same word.\n"
                    "4) SPECIFIC: name the concept explicitly. "
                    "BANNED vague patterns: 'tell me more', 'what else', 'what is next', 'next step after', 'summarize everything'.\n"
                    "5) SHORT: 40-120 characters each, single sentence, ends with '?'.\n"
                    "If the concepts + conversation only support 1-2 strong questions, return only those. "
                    "Output ONLY a JSON array of strings. No other text."
                ),
                HumanMessage(
                    content=f"Concepts (only allowed topics):\n{concepts_txt}"
                    f"\n\n{convo_txt}"
                    f"\n\nUser question (do NOT repeat it): {q[:500]}"
                    f"\nTutor answer (find what it left uncovered): {a[:2000]}"
                ),
            ]
        )
        raw = res.content.strip().replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return []
        # Programmatic quality gates: suggestions must stay inside
        # concepts + conversation vocabulary (prompt alone is not enough).
        allowed_txt = f"{concepts_txt}\n{convo_txt}".lower()
        allowed_words = {w for w in re.findall(r"[a-z0-9]+", allowed_txt) if len(w) >= 4}
        stop = {"what", "which", "when", "with", "from", "that", "this", "have", "more", "about", "does", "example", "give", "explain"}
        allowed_words -= stop
        out = []
        seen = set()
        first_words = set()
        for item in parsed:
            if not isinstance(item, str):
                continue
            s = " ".join(item.split()).strip()
            if not s:
                continue
            if s[-1] not in "?!":
                s += "?"
            # Chip readability: not too short (vague) nor too long (truncated).
            if len(s) < 40 or len(s) > 120:
                continue
            if _is_vague(s):
                continue
            key = s.lower()
            if key in seen:
                continue
            # Novelty: reject near-duplicates of the just-asked question.
            if _jaccard(s, q) > 0.55:
                continue
            # Novelty vs siblings: reject near-duplicates within the set.
            if any(_jaccard(s, prev) > 0.6 for prev in out):
                continue
            # Diversity: don't start two questions with the same word.
            fw = key.split()[0] if key.split() else ""
            if fw in first_words:
                continue
            # Grounded in conversations + concepts only.
            q_words = {w for w in re.findall(r"[a-z0-9]+", key) if len(w) >= 4} - stop
            if len(q_words & allowed_words) < 2:
                continue
            seen.add(key)
            first_words.add(fw)
            out.append(s)
            if len(out) >= 3:
                break
        return out
    except Exception as e:
        logger.warning(f"[tutor.suggest] skipped: {e}")
        return []


async def detect_intent(state: dict) -> dict:
    logger.info(f"[tutor.intent] project_id={state.get('project_id', '?')} entry")
    # Quick actions carry placeholder user text ("Generating…") with no
    # topic — the classifier would read small-talk and misroute them to
    # general_chat, skipping their directives. Go knowledge directly.
    try:
        from app.ai.actions import VALID_ACTIONS as _VA
        if (state.get("action_id") or "") in _VA:
            logger.info("[tutor.intent] intent=knowledge (quick action, classifier skipped)")
            return {"intent": INTENT_KNOWLEDGE}
    except Exception:
        pass
    question = state.get("user_question", "")
    # Identity / personal-memory questions are conversational, not document
    # lookups — route them to the general path so they are never rejected
    # by the strict RAG evidence gate.
    try:
        from app.services.learning_service import is_name_question as _is_name_q

        if _is_name_q(question):
            logger.info("[tutor.intent] intent=general (name question)")
            return {"intent": INTENT_GENERAL}
    except Exception:
        pass
    llm = get_llm()
    try:
        res = await llm.ainvoke(
            [
                SystemMessage(
                    content="Classify the user's message. Output ONLY one word: "
                    f"'{INTENT_GENERAL}' if it is general conversation "
                    "(greeting, small talk, asking what you can do, thanks, goodbye, "
                    "or asking about themselves such as their name / preferences), "
                    f"or '{INTENT_KNOWLEDGE}' if it asks about specific learning material or knowledge. "
                    "No other text."
                ),
                HumanMessage(content=question),
            ]
        )
        label = res.content.strip().lower()
        intent = INTENT_GENERAL if INTENT_GENERAL in label else INTENT_KNOWLEDGE
    except Exception as e:
        logger.warning(f"[tutor.intent] classifier failed, defaulting to knowledge: {e}")
        intent = INTENT_KNOWLEDGE
    logger.info(f"[tutor.intent] intent={intent}")
    return {"intent": intent}


def _lookup_user_name(user_id_str: str, project_id_str: str) -> str:
    """Best-effort stored-name lookup. Never raises; returns '' when unknown."""
    try:
        import uuid as _uuid

        from app.db.models.learning import LearningContext
        from app.services.learning_service import user_name_from_rows

        db = SessionLocal()
        try:
            rows = (
                db.query(LearningContext)
                .filter(LearningContext.user_id == _uuid.UUID(user_id_str),
                        LearningContext.project_id == _uuid.UUID(project_id_str))
                .order_by(LearningContext.updated_at.desc())
                .limit(50)
                .all()
            )
            return user_name_from_rows(rows) or ""
        finally:
            db.close()
    except Exception:
        return ""


async def general_chat(state: dict) -> dict:
    logger.info(f"[tutor.general] project_id={state.get('project_id', '?')} entry")
    from app.services.learning_service import (
        RECENT_MESSAGE_COUNT as _RECENT,
        extract_user_name as _extract_name,
        is_name_question as _is_name_q,
    )

    question = state.get("user_question", "")
    user_id = str(state.get("user_id", ""))
    project_id = str(state.get("project_id", ""))

    # Fast path: the current message itself introduces the name.
    introduced = _extract_name(question)
    stored = state.get("user_name") or ""
    if not stored and user_id and project_id:
        stored = _lookup_user_name(user_id, project_id)
    display_name = introduced or stored

    # Direct answer for "What is my name?" when we know it — no LLM needed,
    # so the answer is deterministic and never a hallucinated "I don't know".
    if _is_name_q(question):
        if display_name:
            answer = f"Your name is {display_name}."
        else:
            answer = "I don't know your name yet — what should I call you?"
        logger.info("[tutor.general] answered name question directly")
        return {"final_answer": answer, "messages": [AIMessage(content=answer)],
                "user_name": display_name or "", "suggested_questions": []}

    llm = get_llm()
    history_msgs = list(state.get("messages") or [])[-_RECENT:]
    name_line = f"The user's name is {display_name}. Address them by name naturally." if display_name else "The user has not shared their name yet."
    res = await llm.ainvoke(
        [
            SystemMessage(
                content="You are a friendly AI Study Companion. The user is chatting casually "
                "(greeting, asking what you can do, etc.). Reply conversationally and briefly. "
                "Mention you can answer questions grounded in their uploaded project materials, "
                "quiz them, and track their concept mastery. "
                f"Personalization: {name_line} If the user just told you their name, "
                "acknowledge it warmly and confirm you will remember it."
            ),
            *history_msgs,
            HumanMessage(content=question),
        ]
    )
    logger.info(f"[tutor.general] done")
    # General/small-talk turns are never grounded in documents, so any
    # suggested question would risk a rejection on click — return none.
    return {"final_answer": res.content, "messages": [res],
            "user_name": display_name or "", "citations": [],
            "suggested_questions": []}


def retrieve_context(state: dict) -> dict:
    # RAG pipeline: Gemini query embedding -> pgvector cosine search,
    # top-5 chunks strictly filtered by project_id.
    # Quick actions carry placeholder user text ("Generating…") with no
    # topic — retrieve on the most recent real human turn instead so the
    # turn grounds in what was actually discussed.
    query = state["user_question"]
    try:
        from app.ai.actions import VALID_ACTIONS as _VQ
        if (state.get("action_id") or "") in _VQ:
            human = [m.content.strip() for m in (state.get("messages") or [])
                     if getattr(m, "type", "") == "human" and (m.content or "").strip()]
            if human:
                query = human[-1][:500]
    except Exception:
        pass
    embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        google_api_key=settings.GOOGLE_API_KEY,
        output_dimensionality=768,
    )
    query_vector = embeddings.embed_query(query)
    db = SessionLocal()
    try:
        rows = (
            db.query(DocumentChunk, Document.file_name)
            .join(Document, Document.id == DocumentChunk.document_id)
            .filter(DocumentChunk.project_id == uuid.UUID(state["project_id"]))
            .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            .limit(5)
            .all()
        )
        context = [f"[Source: Page {c.page_number}] {c.content}" for c, _ in rows]
        sources = [
            {
                "chunk_id": str(c.id),
                "document_id": str(c.document_id),
                "file_name": file_name,
                "page_number": c.page_number,
                "content": c.content,
            }
            for c, file_name in rows
        ]
    finally:
        db.close()
    return {"retrieved_context": context, "retrieved_sources": sources}

    # COLIVARA ALTERNATIVE - COMMENTED OUT (revert by swapping these blocks)
    # Visual RAG retrieval — ColiVara search -> OCR pages -> text.
    # Return shape is unchanged so the grade/generate nodes and their
    # prompt templates work exactly as before, with page sources kept.
    # from app.services.document_retrieval_service import retrieve_and_extract_context
    #
    # _, ocr_results = retrieve_and_extract_context(state["user_question"])
    # context = [
    #     f"[Source: Page {r['page_id']}] {r['extracted_text']}" for r in ocr_results
    # ]
    # return {"retrieved_context": context}


async def grade_documents(state: dict) -> dict:
    # Fail open on provider errors: generate_answer's own prompt still
    # refuses when context is truly insufficient, so a grader outage
    # degrades to "try to answer" instead of a 500.
    try:
        llm = get_llm()
        res = await llm.ainvoke(
            [
                SystemMessage(
                    content="You evaluate whether the provided Context is sufficient to answer the user's question. "
                    "Output ONLY the word 'yes' or the word 'no'. No other text."
                ),
                HumanMessage(
                    content=f"Question: {state['user_question']}\n\nContext:\n"
                    + "\n".join(state.get("retrieved_context", []))
                ),
            ]
        )
    except Exception as e:
        logger.warning(f"[tutor.grade] grader failed, failing open: {e}")
        return {"sufficient_evidence": True}
    return {"sufficient_evidence": res.content.strip().lower() == "yes"}


def reject_answer(state: dict) -> dict:
    # Fallback turn: creative message only, no suggested questions.
    return {"final_answer": REJECT_MESSAGE, "messages": [AIMessage(content=REJECT_MESSAGE)],
            "citations": [], "suggested_questions": []}


def retrieve_learning_context(state: dict) -> dict:
    """Fast, sync, failure-safe: conversation summary + freshest learner
    memory + recent assessment stats. Memory is loaded by recency, never
    filtered by the current question — no question-matching here. Never
    raises — on any failure the tutor proceeds with RAG + recent messages
    only."""
    empty = {"conversation_summary": "", "relevant_learning_context": [],
             "relevant_assessment_context": "", "user_name": state.get("user_name") or ""}
    try:
        import uuid as _uuid

        from app.db.models.assessment import Concept
        from app.db.models.chat import ChatSession
        from app.db.models.learning import LearningContext
        from app.db.models.mastery import QuizHistory
        from app.services.learning_service import (
            ALWAYS_TYPE_CAP, ALWAYS_TYPES, RECENT_MESSAGE_COUNT,
            extract_user_name, format_assessment, get_summary,
            render_memory_lines, user_name_from_rows, upsert_memory,
        )

        project_id = _uuid.UUID(state["project_id"])
        user_id = _uuid.UUID(state["user_id"])
        question = state.get("user_question", "")
        db = SessionLocal()
        try:
            # Synchronous fast path: persist a self-introduced name NOW so a
            # follow-up "What is my name?" works even if Celery is down.
            # Concept-less + event-less upserts can't dedup, so update the
            # latest user_fact row in place instead of inserting duplicates.
            try:
                introduced = extract_user_name(question)
                if introduced:
                    from datetime import datetime as _dt

                    existing_fact = (
                        db.query(LearningContext)
                        .filter(LearningContext.user_id == user_id,
                                LearningContext.project_id == project_id,
                                LearningContext.type == "user_fact")
                        .order_by(LearningContext.updated_at.desc())
                        .first()
                    )
                    if existing_fact is not None:
                        existing_fact.content = f"User's name is {introduced}"
                        existing_fact.confidence = 0.95
                        existing_fact.updated_at = _dt.utcnow()
                        db.commit()
                    else:
                        upsert_memory(
                            db, user_id=user_id, project_id=project_id,
                            type="user_fact", concept_id=None,
                            content=f"User's name is {introduced}",
                            confidence=0.95, source="conversation",
                            source_id=None,
                        )
            except Exception as ne:
                logger.warning(f"[tutor.memory] name persist skipped: {ne}")

            session = None
            session_id_raw = state.get("chat_session_id")
            if session_id_raw:
                try:
                    candidate = db.get(ChatSession, _uuid.UUID(str(session_id_raw)))
                    # Never leak another project's summary: scope to this project.
                    if candidate is not None and candidate.project_id == project_id:
                        session = candidate
                except (ValueError, AttributeError):
                    session = None
            if session is None:
                session = db.query(ChatSession).filter(ChatSession.project_id == project_id).first()
            summary, _ = get_summary(db, session.id) if session else (None, None)

            concepts = db.query(Concept).filter(Concept.project_id == project_id).all()
            concept_names = {c.id: c.name for c in concepts}

            rows = (
                db.query(LearningContext)
                .filter(LearningContext.user_id == user_id,
                        LearningContext.project_id == project_id)
                .order_by(LearningContext.updated_at.desc())
                .limit(50)
                .all()
            )
            user_name = user_name_from_rows(rows) or extract_user_name(question) or ""
            # No question-based filtering: always-on profile rows first, then
            # the freshest remaining rows, bounded so prompts stay small.
            selected = [r for r in rows if r.type in ALWAYS_TYPES][: ALWAYS_TYPE_CAP * 2]
            for r in rows:
                if r in selected or len(selected) >= ALWAYS_TYPE_CAP * 2 + 4:
                    continue
                selected.append(r)
            memory_text = render_memory_lines(selected, concept_names)

            # Recent assessment stats across all concepts (no question match).
            assessment_text = ""
            hist = (
                db.query(QuizHistory)
                .filter(QuizHistory.user_id == user_id)
                .order_by(QuizHistory.created_at.desc())
                .limit(60)
                .all()
            )
            by_concept = {}
            for h in hist:
                if h.concept_id is None:
                    continue
                by_concept.setdefault(h.concept_id, []).append(h)
            stats = []
            for cid, items in list(by_concept.items())[:6]:
                recent = items[:10]
                correct = sum(1 for i in recent if i.is_correct)
                mistake = next((i.evaluator_feedback for i in recent if not i.is_correct and i.evaluator_feedback), None)
                stats.append({"concept": concept_names.get(cid, "Unknown"),
                              "correct": correct, "total": len(recent),
                              "last_mistake": mistake})
            assessment_text = format_assessment(stats)
            return {
                "conversation_summary": summary or "",
                "relevant_learning_context": memory_text.split("\n") if memory_text else [],
                "relevant_assessment_context": assessment_text,
                "user_name": user_name,
            }
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"[tutor.memory] retrieval failed, continuing without: {e}")
        return empty


# In-window history compression: bounded verbatim tail + high-priority
# bullets for the rest. Keeps answer prompts small on long threads.
HISTORY_VERBATIM_TAIL = 6
HISTORY_CHAR_BUDGET = 6000


async def compress_history(state: dict) -> dict:
    """Distill older in-window assistant turns to high-priority bullets.

    Only the most recent HISTORY_VERBATIM_TAIL messages travel verbatim to
    the answer prompt; older ASSISTANT turns are compressed to the important
    points (key definitions, conclusions, facts, open threads). User
    questions are never included — no questions in, no questions out.
    Greetings, small-talk, repetition, and drill placeholder bubbles
    ("Generating…") are dropped. No LLM call when the window already fits
    the budget — this node is nearly free on short threads.
    """
    try:
        msgs = list(state.get("messages") or [])
        if len(msgs) <= HISTORY_VERBATIM_TAIL:
            if sum(len(m.content or "") for m in msgs) <= HISTORY_CHAR_BUDGET:
                return {"history_summary": ""}
        older = msgs[:-HISTORY_VERBATIM_TAIL] if len(msgs) > HISTORY_VERBATIM_TAIL else msgs
        older = [m for m in older if getattr(m, "type", "") != "human"]
        older_txt = "\n".join(
            f"{getattr(m, 'type', 'msg')}: {(m.content or '')[:800]}" for m in older
        ).strip()
        if not older_txt:
            return {"history_summary": ""}
        llm = get_llm()
        res = await llm.ainvoke(
            [
                SystemMessage(
                    content="Compress these assistant answers into 3-6 bullets covering "
                    "ONLY high-priority content about the study materials: key "
                    "definitions, conclusions, facts, and open threads. Do not "
                    "include user questions — answers only. Drop anything "
                    "off-topic or unrelated, "
                    "greetings, small-talk, repetition, status/placeholder messages "
                    "(e.g. 'Generating…'), and failed turns. Output ONLY the "
                    "bullets, no intro or outro."
                ),
                HumanMessage(content=older_txt[:8000]),
            ]
        )
        return {"history_summary": (res.content or "").strip()[:2000]}
    except Exception as e:
        logger.warning(f"[tutor.compress] skipped: {e}")
        return {"history_summary": ""}


async def generate_answer(state: dict) -> dict:
    project_id = state.get("project_id", "?")
    logger.info(f"[tutor.generate] project_id={project_id} start")
    # Name questions that slipped to the knowledge path are still answered
    # from memory — they must never hit the document-evidence gate.
    try:
        from app.services.learning_service import is_name_question as _is_name_q2

        if _is_name_q2(state.get("user_question", "")):
            known = (state.get("user_name") or "").strip()
            if not known:
                known = _lookup_user_name(str(state.get("user_id", "")), str(project_id))
            if known:
                answer = f"Your name is {known}."
                return {"final_answer": answer, "messages": [AIMessage(content=answer)],
                        "citations": [], "user_name": known, "suggested_questions": []}
    except Exception:
        pass
    llm = get_llm()
    context = "\n".join(state.get("retrieved_context", []))

    # Practice turns are chat-only drills: they must never move mastery.
    from app.ai.actions import PRACTICE as _PRACTICE_ACTION
    practice_turn = (state.get("action_id") or "") == _PRACTICE_ACTION

    # Silent mastery signal: does the user demonstrate understanding?
    # Skipped entirely for practice turns (see above).
    if not practice_turn:
        try:
            history_txt = "\n".join(
                f"{m.type}: {m.content[:500]}" for m in (state.get("messages") or [])[-6:]
            )
            sig_res = await llm.ainvoke(
                [
                    SystemMessage(
                        content="Does the user demonstrate understanding of any core concepts in this interaction? "
                        "If yes, output ONLY JSON like {\"concept_name\": \"X\", \"confidence_score\": 80}. "
                        "If no, output null. No other text."
                    ),
                    HumanMessage(
                        content=f"Question: {state.get('user_question')}\nContext:\n{context[:3000]}\nHistory:\n{history_txt}"
                    ),
                ]
            )
            raw = sig_res.content.strip().replace("```json", "").replace("```", "").strip()
            if raw and raw.lower() != "null" and raw.lower() != "none":
                try:
                    signal = ChatMasterySignal(**json.loads(raw))
                    from app.tasks.concept_tasks import update_mastery_from_chat_task

                    update_mastery_from_chat_task.delay(
                        str(project_id), signal.concept_name, float(signal.confidence_score)
                    )
                    logger.info(f"[tutor.generate] mastery signal project={project_id} concept={signal.concept_name}")
                except Exception as pe:
                    logger.warning(f"[tutor.generate] mastery parse/dispatch skipped: {pe}")
        except Exception as e:
            logger.warning(f"[tutor.generate] silent eval failed project={project_id}: {e}")
    else:
        logger.info(f"[tutor.generate] practice turn — mastery signal skipped project={project_id}")

    summary = state.get("conversation_summary") or ""
    memory_lines = state.get("relevant_learning_context") or []
    assessment = state.get("relevant_assessment_context") or ""
    # Bounded verbatim tail — older turns arrive via history_summary
    # (compress_history node), so long threads stay cheap.
    history_msgs = list(state.get("messages") or [])[-HISTORY_VERBATIM_TAIL:]
    if practice_turn:
        # Practice drills must never quiz greetings, placeholders, or
        # off-topic turns: keep only material-related human questions.
        # Assistant answers always stay (they carry the study content).
        from app.services.learning_service import (
            concept_matches, concept_vocabulary, is_noise_message,
            significant_words,
        )
        try:
            import uuid as _uuid2
            from app.db.models.assessment import Concept as _Concept
            _db = SessionLocal()
            try:
                _names = [c.name for c in _db.query(_Concept).filter(
                    _Concept.project_id == _uuid2.UUID(str(project_id))).all()]
            finally:
                _db.close()
        except Exception:
            _names = []
        _vocab = concept_vocabulary(_names)

        def _material_question(text):
            t = (text or "").strip()
            if not t or is_noise_message(t):
                return False
            if any(concept_matches(t, n) for n in _names):
                return True
            return len(significant_words(t) & _vocab) >= 1

        history_msgs = [m for m in history_msgs
                        if getattr(m, "type", "") != "human" or _material_question(m.content or "")]
    compressed_history = (state.get("history_summary") or "").strip()
    user_name = (state.get("user_name") or "").strip()
    identity_line = (
        f"The user's name is {user_name}. Use it naturally when relevant "
        "(e.g. when they ask who they are, confirm: 'Your name is X.')."
        if user_name else
        "The user has not shared their name yet. If asked for their name, say you don't know it yet and ask what to call them."
    )

    system_content = (
        "You are an AI Study Companion. Answer the user's question in your own words, "
        "SYNTHESIZING the key points from the provided Context into a clear, structured response. "
        "NEVER copy chunk text verbatim — always paraphrase and combine related points. "
        "Use ONLY the provided Context. If the context does not contain the answer, state "
        "exactly: 'That's outside what your uploaded materials cover right now — "
        "try asking about one of your project topics, and I'll explore it with you.' "
        "Return a clean, well-structured Markdown response (GitHub-flavored Markdown): "
        "use Markdown headings (##, ###) to organize longer explanations — never use # H1, "
        "start at ##; use bullet lists for groups of related concepts; use numbered lists "
        "for sequential procedures; use Markdown tables when comparing concepts or presenting "
        "structured information; use fenced Markdown code blocks with a language tag for "
        "programming code; keep paragraphs concise. Match the depth to the question — a simple "
        "question deserves a short answer, not a full document. "
        "Do not return HTML. Do not return JSON. Do not expose internal reasoning. "
        "Do not fabricate citations. "
        "End every factual claim with a citation exactly like [Source: Page 3], using the page "
        "numbers shown in the Context. Example: 'JWTs are signed tokens [Source: Page 2].'"
        "The recent conversation follows as message history; a summary of older conversation "
        "may also be provided. "
        "Persistent learner context below is project-scoped background: use it ONLY when relevant "
        "to this question (e.g. emphasize a known weakness naturally), never let it override "
        "document evidence, and never mention memory internals."
        f"\n\nUser identity:\n{identity_line}"
        f"\n\nConversation summary (older context):\n{summary or 'None yet.'}"
        f"\n\nCompressed recent history (high-priority points only):\n{compressed_history or 'None.'}"
        f"\n\nPersistent learner context:\n{chr(10).join(memory_lines) if memory_lines else 'None.'}"
        f"\n\nRelevant assessment history:\n{assessment or 'None.'}"
        f"\n\nContext:\n{context}"
    )
    # Quick-action shaping (summarize / deep dive / flashcards / practice):
    # same RAG + conversation-memory pipeline, only the response directive
    # changes (see app.ai.actions).
    action_hint = (state.get("action_hint") or "").strip()
    if action_hint:
        system_content += f"\n\nActive quick-action guidance:\n{action_hint}"
    res = await llm.ainvoke(
        [
            SystemMessage(content=system_content),
            *history_msgs,
            HumanMessage(content=state["user_question"]),
        ]
    )
    logger.info(f"[tutor.generate] project_id={project_id} done")
    citations = _build_citations(res.content, state.get("retrieved_sources", []))
    # Pass conversation + concepts context so suggestions reuse known topics.
    # Clicking one stays inside the same concepts/conversation scope.
    suggestions = await _suggest_followups(
        state.get("user_question", ""), res.content,
        project_id=str(project_id),
        conversation_summary=summary,
        learning_lines=memory_lines,
    )
    return {"final_answer": res.content, "messages": [res], "citations": citations,
            "suggested_questions": suggestions}


def _extract_cited_pages(answer: str) -> set[int]:
    """Extract all cited page numbers, tolerating LLM format drift.

    Handles: [Source: Page 3], [source: page 3], [Sources: Pages 2, 3],
    [Source: Pages 2-4], [Source p. 5], [Source pp. 5-6], etc.
    Ranges are expanded so [Pages 2-4] -> {2, 3, 4}.
    """
    if not answer:
        return set()
    pages: set[int] = set()
    # Match bracketed source markers case-insensitively.
    # e.g. [Source: Page 3] / [Sources: Pages 2, 3] / [source p. 5-7]
    marker_re = re.compile(
        r"\[\s*sources?\s*:?\s*(?:pages?|pps?\.?|p\.?)?\s*([0-9][0-9\s,;.&\-–—]*)s?\]",
        re.IGNORECASE,
    )
    for m in marker_re.finditer(answer):
        inner = m.group(1)
        # Split on commas/semicolons/ampersands, then expand ranges.
        for chunk in re.split(r"[,;.&]+", inner):
            chunk = chunk.strip()
            if not chunk:
                continue
            range_m = re.match(r"^(\d+)\s*[-–—]\s*(\d+)$", chunk)
            if range_m:
                start, end = int(range_m.group(1)), int(range_m.group(2))
                if start > end:
                    start, end = end, start
                # Guard against absurd ranges (e.g. hallucinated 1-999).
                if end - start > 50:
                    continue
                pages.update(range(start, end + 1))
                continue
            # A chunk may still contain stray spaces ("2 3") — pull all ints.
            for n in re.findall(r"\d+", chunk):
                try:
                    pages.add(int(n))
                except ValueError:
                    continue
    return pages


def _normalize_source(s: dict) -> dict | None:
    """Normalize one retrieved chunk to {file_name, page_number, content}."""
    if not isinstance(s, dict):
        return None
    file_name = (
        s.get("file_name") or s.get("pdf_name") or s.get("document_name")
        or s.get("title") or "Document"
    )
    raw_page = s.get("page_number", s.get("page", s.get("pageNumber")))
    try:
        page = int(raw_page)
    except (TypeError, ValueError):
        return None
    content = s.get("content", s.get("chunk_excerpt", s.get("excerpt", s.get("text", ""))))
    return {"file_name": str(file_name), "page_number": page, "content": str(content or "")}


def _build_citations(answer: str, sources: list) -> list:
    """Match [Source: Page X] markers to retrieved chunks.

    Returns [{pdf_name, page_number, chunk_excerpt}]. Prefers exactly the
    cited pages; falls back to all retrieved chunks when the model omits
    markers, so grounded answers always carry their sources.
    Keyed by (document, page) so two PDFs with the same page number both
    survive instead of collapsing into one card.
    """
    normalized = []
    for s in sources or []:
        n = _normalize_source(s)
        if n is not None:
            normalized.append(n)
    if not normalized:
        return []

    cited_pages = _extract_cited_pages(answer or "")

    cards: dict[tuple, dict] = {}
    for s in normalized:
        page = s["page_number"]
        if cited_pages and page not in cited_pages:
            continue
        key = (s["file_name"], page)
        if key in cards:
            continue
        content = s["content"]
        cards[key] = {
            "pdf_name": s["file_name"],
            "page_number": page,
            "chunk_excerpt": content[:220] + ("..." if len(content) > 220 else ""),
        }
    # If the model cited pages we never retrieved (hallucinated numbers),
    # every chunk was filtered out — fall back to all chunks rather than
    # showing zero sources for a grounded answer.
    if not cards and normalized:
        for s in normalized:
            key = (s["file_name"], s["page_number"])
            if key in cards:
                continue
            content = s["content"]
            cards[key] = {
                "pdf_name": s["file_name"],
                "page_number": s["page_number"],
                "chunk_excerpt": content[:220] + ("..." if len(content) > 220 else ""),
            }
    return [cards[k] for k in sorted(cards, key=lambda t: (t[1], t[0].lower()))]
