from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List
from langchain_core.messages import HumanMessage, AIMessage
from app.db.session import get_db
from app.api.deps import get_owned_project
from app.db.models.project import Project
from app.db.models.chat import ChatSession, Message
from app.schemas.chat import MessageOut, ChatSessionOut
from app.ai.tutor_graph import tutor_app

router = APIRouter()

class TutorRequest(BaseModel):
    question: str = Field(..., min_length=1)

class TutorResponse(BaseModel):
    answer: str
    chat_session_id: str
    message_id: str

def get_or_create_session(project_id, db: Session) -> ChatSession:
    session = db.query(ChatSession).filter(ChatSession.project_id == project_id).first()
    if not session:
        session = ChatSession(project_id=project_id)
        db.add(session)
        db.commit()
        db.refresh(session)
    return session

@router.post("/{project_id}/tutor", response_model=TutorResponse)
async def tutor_chat(
    body: TutorRequest,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    chat_session = get_or_create_session(project.id, db)

    history = db.query(Message).filter(Message.chat_session_id == chat_session.id).order_by(Message.created_at).all()
    messages_for_graph = []
    for m in history:
        if m.role == "user":
            messages_for_graph.append(HumanMessage(content=m.content))
        else:
            messages_for_graph.append(AIMessage(content=m.content))

    user_msg = Message(chat_session_id=chat_session.id, role="user", content=body.question)
    db.add(user_msg)
    db.commit()

    config = {"configurable": {"thread_id": str(chat_session.id)}}
    result = await tutor_app.ainvoke(
        {"user_question": body.question, "project_id": str(project.id), "messages": messages_for_graph, "final_answer": ""},
        config=config,
    )
    answer = result["final_answer"]

    assistant_msg = Message(chat_session_id=chat_session.id, role="assistant", content=answer)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return {"answer": answer, "chat_session_id": str(chat_session.id), "message_id": str(assistant_msg.id)}

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
