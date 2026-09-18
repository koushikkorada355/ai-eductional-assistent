from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Literal
from uuid import UUID
from langchain_core.messages import HumanMessage, AIMessage
from app.db.session import get_db
from app.api.deps import get_owned_project, get_current_user
from app.db.models.project import Project
from app.db.models.user import User
from app.db.models.chat import ChatSession, Message
from app.schemas.chat import (
    MessageOut, ChatSessionOut, ConversationCreate, ConversationUpdate,
    ConversationOut,
)
from app.ai.graphs.tutor_graph import tutor_app
from app.ai.actions import get_action_hint, parse_flashcards, parse_practice_mcq, CREATE_FLASHCARDS, PRACTICE
from app.services.ai_usage_service import track_ai_call
from loguru import logger

router = APIRouter()

DEFAULT_TITLE = "New conversation"

QuickAction = Literal["summarize", "deep_dive", "create_flashcards", "practice"]


def _provider_error(e: Exception) -> Optional[HTTPException]:
    """Map LLM provider failures to friendly HTTP statuses (never raw 500s).

    Rate limits (Groq 429 / OpenAI-compatible 429) → 429 with retry hint;
    other provider errors → 502. Everything else returns None (re-raise).
    """
    name = type(e).__name__
    msg = str(e)
    try:
        from groq import RateLimitError as _GroqRL
        if isinstance(e, _GroqRL):
            return HTTPException(status_code=429, detail="AI is busy right now (rate limit). Please wait a moment and try again.")
    except Exception:
        pass
    try:
        from openai import RateLimitError as _OpenAIRL
        if isinstance(e, _OpenAIRL):
            return HTTPException(status_code=429, detail="AI is busy right now (rate limit). Please wait a moment and try again.")
    except Exception:
        pass
    if "RateLimit" in name or " 429" in msg or "rate_limit" in msg.lower():
        return HTTPException(status_code=429, detail="AI is busy right now (rate limit). Please wait a moment and try again.")
    if "APIStatusError" in name or "APIConnectionError" in name or "APITimeout" in name:
        logger.warning(f"[tutor] provider error mapped to 502: {name}: {msg[:200]}")
        return HTTPException(status_code=502, detail="AI provider had a hiccup. Please try again in a moment.")
    return None


class TutorRequest(BaseModel):
    question: str = Field(..., min_length=1)
    conversation_id: Optional[UUID] = None
    # Quick action shaping this turn (summarize/deep_dive/
    # create_flashcards/practice). Same RAG pipeline; only prompt guidance
    # changes. Practice renders MCQs inline in chat and never touches mastery.
    action: Optional[QuickAction] = None


class TutorResponse(BaseModel):
    answer: str
    chat_session_id: str
    message_id: str
    citations: Optional[Any] = None
    # Server-truth title (reflects first-question auto-titling) so the
    # conversation nav updates without an extra round-trip.
    conversation_title: Optional[str] = None
    # Structured flashcards parsed from a create_flashcards turn (session
    # only; the markdown answer remains the persisted record).
    flashcards: Optional[Any] = None
    # Structured MCQs parsed from a practice turn (session only, chat-only
    # drill — nothing is written to quiz tables and mastery is untouched).
    mcq: Optional[Any] = None
    # Follow-up questions shown as clickable chips under the AI response.
    suggested_questions: List[str] = []


def _touch(session: ChatSession, db: Session):
    session.updated_at = datetime.utcnow()
    db.add(session)


def _auto_title(session: ChatSession, question: str) -> bool:
    """Derive a readable title from the first real question (no LLM call)."""
    if (session.title or "").strip() not in ("", DEFAULT_TITLE):
        return False
    text = " ".join((question or "").split())
    if not text:
        return False
    title = text[:60].rstrip()
    if len(text) > 60:
        title = title.rsplit(" ", 1)[0] or title
    session.title = title or DEFAULT_TITLE
    return True


def get_or_create_session(project_id, db: Session) -> ChatSession:
    """Legacy helper: most recently active session, or a fresh one."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.project_id == project_id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
        .first()
    )
    if not session:
        session = ChatSession(project_id=project_id, title=DEFAULT_TITLE)
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def _get_owned_conversation(conversation_id: UUID, project: Project, db: Session) -> ChatSession:
    """Fetch a conversation strictly scoped to the project. 404 either way
    so callers can't probe which project a foreign conversation belongs to."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == conversation_id,
                ChatSession.project_id == project.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Conversation not found in this project")
    return session


def _conversation_out(session: ChatSession, db: Session) -> dict:
    count = db.query(Message).filter(Message.chat_session_id == session.id).count()
    last = (
        db.query(Message)
        .filter(Message.chat_session_id == session.id)
        .order_by(Message.created_at.desc())
        .first()
    )
    return {
        "id": session.id,
        "project_id": session.project_id,
        "title": session.title or DEFAULT_TITLE,
        "is_active": session.is_active,
        "created_at": session.created_at,
        "updated_at": session.updated_at or session.created_at,
        "message_count": count,
        "last_message_at": last.created_at if last else None,
        "last_preview": (last.content or "")[:120] if last else None,
    }


def _normalize_citations(raw) -> list:
    """Guarantee the frontend contract: [{pdf_name, page_number, chunk_excerpt}]."""
    if not isinstance(raw, list):
        return []
    out = []
    seen = set()
    for c in raw:
        if not isinstance(c, dict):
            continue
        name = c.get("pdf_name") or c.get("file_name") or c.get("document_name") or "Document"
        try:
            page = int(c.get("page_number", c.get("page")))
        except (TypeError, ValueError):
            continue
        excerpt = c.get("chunk_excerpt", c.get("excerpt", c.get("content", c.get("text", ""))))
        key = (str(name), page)
        if key in seen:
            continue
        seen.add(key)
        out.append({"pdf_name": str(name), "page_number": page, "chunk_excerpt": str(excerpt or "")})
    return sorted(out, key=lambda d: (d["page_number"], d["pdf_name"].lower()))


def _normalize_suggestions(raw) -> list:
    """Guarantee the frontend contract: list of <=3 short question strings."""
    if not isinstance(raw, list):
        return []
    out = []
    seen = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        s = " ".join(item.split()).strip()
        if len(s) < 10:
            continue
        if len(s) > 140:
            s = s[:137].rstrip() + "..."
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= 3:
            break
    return out


def _tutor_ctx(chat_session, question, project, current_user, db, action=None):
    return {"user_id": getattr(current_user, "id", None),
            "project_id": getattr(project, "id", None)}


@track_ai_call("tutor_answer", ctx_fn=_tutor_ctx)
async def _run_tutor_turn(
    chat_session: ChatSession, question: str, project: Project,
    current_user: User, db: Session, action: Optional[str] = None,
) -> dict:
    history = (
        db.query(Message)
        .filter(Message.chat_session_id == chat_session.id)
        .order_by(Message.created_at)
        .all()
    )
    messages_for_graph = []
    for m in history:
        if m.role == "user":
            messages_for_graph.append(HumanMessage(content=m.content))
        else:
            messages_for_graph.append(AIMessage(content=m.content))

    user_msg = Message(chat_session_id=chat_session.id, role="user", content=question)
    db.add(user_msg)
    titled = _auto_title(chat_session, question)
    _touch(chat_session, db)
    db.commit()
    db.refresh(user_msg)

    config = {"configurable": {"thread_id": str(chat_session.id)}}
    result = await tutor_app.ainvoke(
        {"user_question": question, "project_id": str(project.id),
         "user_id": str(current_user.id), "user_name": "",
         "chat_session_id": str(chat_session.id),
         "action_hint": get_action_hint(action),
         "action_id": action or "",
         "messages": messages_for_graph[-10:], "final_answer": ""},
        config=config,
    )
    answer = result["final_answer"]
    citations = _normalize_citations(result.get("citations") or [])
    suggestions = _normalize_suggestions(result.get("suggested_questions") or [])
    flashcards = parse_flashcards(answer) if action == CREATE_FLASHCARDS else []
    practice_mcq = parse_practice_mcq(answer) if action == PRACTICE else []

    assistant_msg = Message(chat_session_id=chat_session.id, role="assistant", content=answer, citations=citations, suggested_questions=suggestions)
    db.add(assistant_msg)
    _touch(chat_session, db)
    db.commit()
    db.refresh(assistant_msg)
    if titled:
        db.refresh(chat_session)

    # Persistent learning context (background, never blocks the response).
    try:
        from app.tasks.learning_tasks import (
            summarize_conversation_task, extract_learning_context_task,
        )
        summarize_conversation_task.delay(str(chat_session.id))
        extract_learning_context_task.delay(str(chat_session.id), str(user_msg.id))
    except Exception:
        pass

    return {"answer": answer, "chat_session_id": str(chat_session.id), "message_id": str(assistant_msg.id), "citations": citations,
            "conversation_title": chat_session.title or DEFAULT_TITLE,
            "flashcards": flashcards or None, "mcq": practice_mcq or None, "suggested_questions": suggestions}


# ---------------------------------------------------------------------------
# Multi-conversation endpoints (canonical)
# ---------------------------------------------------------------------------

@router.get("/{project_id}/conversations", response_model=List[ConversationOut])
def list_conversations(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.project_id == project.id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
        .all()
    )
    return [_conversation_out(s, db) for s in sessions]


@router.post("/{project_id}/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(
    body: ConversationCreate,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    title = (body.title or "").strip() or DEFAULT_TITLE
    session = ChatSession(project_id=project.id, title=title[:200])
    db.add(session)
    db.commit()
    db.refresh(session)
    return _conversation_out(session, db)


@router.patch("/{project_id}/conversations/{conversation_id}", response_model=ConversationOut)
def rename_conversation(
    conversation_id: UUID,
    body: ConversationUpdate,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title must not be empty")
    session = _get_owned_conversation(conversation_id, project, db)
    session.title = title[:200]
    _touch(session, db)
    db.commit()
    db.refresh(session)
    return _conversation_out(session, db)


@router.delete("/{project_id}/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: UUID,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    session = _get_owned_conversation(conversation_id, project, db)
    db.delete(session)
    db.commit()
    return None


@router.get("/{project_id}/conversations/{conversation_id}/messages", response_model=List[MessageOut])
def list_conversation_messages(
    conversation_id: UUID,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    session = _get_owned_conversation(conversation_id, project, db)
    return (
        db.query(Message)
        .filter(Message.chat_session_id == session.id)
        .order_by(Message.created_at)
        .all()
    )


@router.post("/{project_id}/conversations/{conversation_id}/tutor", response_model=TutorResponse)
async def conversation_tutor_chat(
    conversation_id: UUID,
    body: TutorRequest,
    project: Project = Depends(get_owned_project),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _get_owned_conversation(conversation_id, project, db)
    try:
        return await _run_tutor_turn(session, body.question, project, current_user, db, action=body.action)
    except HTTPException:
        raise
    except Exception as e:
        mapped = _provider_error(e)
        if mapped is not None:
            raise mapped
        raise


# ---------------------------------------------------------------------------
# Legacy endpoints (kept for backward compatibility)
# ---------------------------------------------------------------------------

@router.post("/{project_id}/tutor", response_model=TutorResponse)
async def tutor_chat(
    body: TutorRequest,
    project: Project = Depends(get_owned_project),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.conversation_id is not None:
        chat_session = _get_owned_conversation(body.conversation_id, project, db)
    else:
        chat_session = get_or_create_session(project.id, db)
    try:
        return await _run_tutor_turn(chat_session, body.question, project, current_user, db, action=body.action)
    except HTTPException:
        raise
    except Exception as e:
        mapped = _provider_error(e)
        if mapped is not None:
            raise mapped
        raise

@router.get("/{project_id}/chat", response_model=ChatSessionOut)
def get_chat_session(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    return get_or_create_session(project.id, db)

@router.get("/{project_id}/messages", response_model=List[MessageOut])
def list_messages(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    chat_session = get_or_create_session(project.id, db)
    return db.query(Message).filter(Message.chat_session_id == chat_session.id).order_by(Message.created_at).all()
