"""Admin read-only endpoints for the AI Learning Operations Center.

Additive only. Every route requires role == 'admin'. No existing endpoint is
modified in a breaking way — new keys are added, existing keys are kept.

Where platform instrumentation does not exist (token usage, latency, cost,
recommendations log), endpoints report honestly instead of fabricating data.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from math import ceil
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.db.models.assessment import (
    Assignment,
    AssignmentSubmission,
    Concept,
    Quiz,
    QuizQuestion,
)
from app.db.models.chat import ChatSession, Message
from app.db.models.document import Document
from app.db.models.mastery import MasteryHistory, QuizHistory
from app.db.models.ai_usage import AIUsage
from app.db.models.project import Project
from app.db.models.space import Space
from app.db.models.user import User
from app.db.session import get_db
from app.utils.pagination import MAX_PAGE_SIZE, PageOut, paginate_list, paginate_query, page_envelope

router = APIRouter()

ACTIVE_DAYS = 30


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if (current_user.role or "user") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def _display_name(u: User) -> str:
    if getattr(u, "name", None):
        return u.name
    return (u.email or "?").split("@")[0]


def _maps(db: Session):
    """Shared lookup maps so each admin request fans out in Python, not N+1 SQL."""
    spaces = db.query(Space).all()
    projects = db.query(Project).all()
    users = {u.id: u for u in db.query(User).all()}
    space_by_id = {s.id: s for s in spaces}
    project_by_id = {p.id: p for p in projects}
    space_user = {s.id: s.user_id for s in spaces}
    project_user = {}
    for p in projects:
        uid = space_user.get(p.space_id)
        if uid is not None:
            project_user[p.id] = uid
    return users, space_by_id, project_by_id, project_user


def _user_last_active(db: Session, user_id, project_user: dict) -> Optional[datetime]:
    """Latest timestamp across everything the user owns. None when inactive."""
    stamps = []
    user_spaces = db.query(Space).filter(Space.user_id == user_id).all()
    stamps += [s.created_at for s in user_spaces if s.created_at]
    space_ids = [s.id for s in user_spaces]
    user_projects = (
        db.query(Project).filter(Project.space_id.in_(space_ids)).all() if space_ids else []
    )
    stamps += [p.created_at for p in user_projects if p.created_at]
    project_ids = [p.id for p in user_projects]
    if project_ids:
        docs = db.query(Document).filter(Document.project_id.in_(project_ids)).all()
        stamps += [d.created_at for d in docs if d.created_at]
        quizzes = db.query(Quiz).filter(Quiz.project_id.in_(project_ids)).all()
        stamps += [q.created_at for q in quizzes if q.created_at]
        sessions = db.query(ChatSession).filter(ChatSession.project_id.in_(project_ids)).all()
        stamps += [s.created_at for s in sessions if s.created_at]
        session_ids = [s.id for s in sessions]
        if session_ids:
            msgs = db.query(Message).filter(Message.chat_session_id.in_(session_ids)).all()
            stamps += [m.created_at for m in msgs if m.created_at]
    user = db.query(User).filter(User.id == user_id).first()
    if user is not None and user.created_at is not None:
        stamps.append(user.created_at)
    return max(stamps) if stamps else None


def _project_progress(db: Session, project_id) -> float:
    concepts = db.query(Concept).filter(Concept.project_id == project_id).all()
    if not concepts:
        return 0.0
    return round(sum(c.mastery_level or 0 for c in concepts) / len(concepts), 1)


def _project_last_active(db: Session, project_id) -> Optional[datetime]:
    stamps = []
    sessions = db.query(ChatSession).filter(ChatSession.project_id == project_id).all()
    stamps += [s.created_at for s in sessions if s.created_at]
    session_ids = [s.id for s in sessions]
    if session_ids:
        msgs = db.query(Message).filter(Message.chat_session_id.in_(session_ids)).all()
        stamps += [m.created_at for m in msgs if m.created_at]
    docs = db.query(Document).filter(Document.project_id == project_id).all()
    stamps += [d.created_at for d in docs if d.created_at]
    quizzes = db.query(Quiz).filter(Quiz.project_id == project_id).all()
    stamps += [q.created_at for q in quizzes if q.created_at]
    return max(stamps) if stamps else None


def _daily_series(dates, days=14):
    buckets = defaultdict(int)
    for d in dates:
        if d:
            buckets[d.date().isoformat()] += 1
    today = datetime.utcnow().date()
    return [
        {"date": (today - timedelta(days=i)).isoformat(),
         "count": buckets.get((today - timedelta(days=i)).isoformat(), 0)}
        for i in range(days - 1, -1, -1)
    ]


def _check_redis() -> dict:
    if not settings.REDIS_URL:
        return {"status": "unavailable", "detail": "REDIS_URL is not configured"}
    try:
        import redis as redis_lib

        client = redis_lib.from_url(settings.REDIS_URL, socket_timeout=2)
        client.ping()
        return {"status": "healthy", "detail": "PING ok"}
    except Exception as e:
        from app.utils.user_errors import short_admin_detail

        return {"status": "unavailable", "detail": short_admin_detail(e)}


def _check_workers() -> dict:
    try:
        from app.tasks.celery_app import celery_app

        ping = celery_app.control.ping(timeout=2)
        if ping:
            names = sorted({k for node in ping for k in node})
            return {"status": "healthy", "detail": f"{len(ping)} worker(s): {', '.join(names)}"}
        return {"status": "degraded", "detail": "No workers replied to ping"}
    except Exception as e:
        from app.utils.user_errors import short_admin_detail

        return {"status": "degraded", "detail": short_admin_detail(e)}


def _ai_providers() -> dict:
    return {
        "inception": {"status": "healthy" if settings.INCEPTION_API_KEY else "unavailable",
                      "detail": f"model={settings.INCEPTION_MODEL}" if settings.INCEPTION_API_KEY else "INCEPTION_API_KEY not set"},
        # Groq path kept (disabled 2026-09-18) for easy switch-back.
        "groq": {"status": "healthy" if settings.GROQ_API_KEY else "unavailable",
                 "detail": f"model={settings.GROQ_MODEL}" if settings.GROQ_API_KEY else "GROQ_API_KEY not set"},
        "google": {"status": "healthy" if settings.GOOGLE_API_KEY else "unavailable",
                   "detail": "embeddings key set" if settings.GOOGLE_API_KEY else "GOOGLE_API_KEY not set"},
    }


@router.get("/admin/overview")
def admin_overview(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users, space_by_id, project_by_id, project_user = _maps(db)
    docs = db.query(Document).all()
    quizzes = db.query(Quiz).all()
    assignments = db.query(Assignment).all()
    messages = db.query(Message).all()
    doc_status, quiz_status, asg_status = defaultdict(int), defaultdict(int), defaultdict(int)
    for d in docs:
        doc_status[d.status] += 1
    for q in quizzes:
        quiz_status[q.status] += 1
    for a in assignments:
        asg_status[a.status] += 1

    cutoff = datetime.utcnow() - timedelta(days=ACTIVE_DAYS)
    active_users = sum(
        1 for u in users.values()
        if (u.created_at and u.created_at >= cutoff)
        or (_user_last_active(db, u.id, project_user) or datetime.min) >= cutoff
    )
    tutor_user = sum(1 for m in messages if m.role == "user")
    tutor_assistant = sum(1 for m in messages if m.role == "assistant")
    questions = db.query(QuizQuestion).all()
    answered = sum(1 for x in questions if x.user_answer is not None)
    # Honest proxy: feature interactions the platform actually stores.
    ai_requests = tutor_assistant + len(quizzes) + len(assignments)

    recent = _recent_activity(db, users, space_by_id, project_by_id, project_user, limit=8)
    return {
        "users": db.query(User).count(),
        "activeUsers": active_users,
        "spaces": db.query(Space).count(),
        "projects": db.query(Project).count(),
        "concepts": db.query(Concept).count(),
        "tutorInteractions": {"total": len(messages), "user": tutor_user, "assistant": tutor_assistant},
        "quizAttempts": {"quizzes": len(quizzes), "questionsAnswered": answered},
        "materials": {"total": len(docs), "byStatus": dict(doc_status)},
        "aiRequests": ai_requests,
        "documents": {"total": len(docs), "byStatus": dict(doc_status)},
        "quizzes": {"total": len(quizzes), "byStatus": dict(quiz_status)},
        "assignments": {"total": len(assignments), "byStatus": dict(asg_status)},
        "messages": db.query(Message).count(),
        "activitySeries": _daily_series(
            [m.created_at for m in messages]
            + [q.created_at for q in quizzes]
            + [d.created_at for d in docs]
            + [u.created_at for u in users.values()]
        ),
        "recentActivity": recent,
        "system": _system_status(db, docs),
    }


def _system_status(db: Session, docs=None) -> dict:
    try:
        db.execute(text("SELECT 1"))
        database = {"status": "healthy", "detail": "SELECT 1 ok"}
    except Exception as e:
        from app.utils.user_errors import short_admin_detail

        database = {"status": "unavailable", "detail": short_admin_detail(e)}
    docs = docs if docs is not None else db.query(Document).all()
    failed = sum(1 for d in docs if d.status == "failed")
    processing = sum(1 for d in docs if d.status in ("queued", "processing"))
    doc_proc = {
        "status": "degraded" if failed else "healthy",
        "detail": f"{processing} queued/processing · {failed} failed",
    }
    return {
        "database": database["status"],
        "uptime": "running",
        "redis": _check_redis(),
        "workers": _check_workers(),
        "aiProviders": _ai_providers(),
        "documentProcessing": doc_proc,
    }


def _recent_activity(db, users, space_by_id, project_by_id, project_user, limit=8):
    """Newest-first cross-table feed. Times use each row's created_at."""
    feed = []

    def who(uid):
        u = users.get(uid)
        return u.email if u else None

    def proj(pid):
        p = project_by_id.get(pid)
        if not p:
            return None, None
        s = space_by_id.get(p.space_id)
        return p.name, who(project_user.get(pid))

    for u in sorted(users.values(), key=lambda x: x.created_at or datetime.min, reverse=True)[:5]:
        feed.append({"id": str(u.id), "type": "user_registered", "label": "User registered",
                     "user": u.email, "project": None, "text": f"{_display_name(u)} joined",
                     "time": u.created_at})
    for s in sorted(db.query(Space).all(), key=lambda x: x.created_at or datetime.min, reverse=True)[:5]:
        feed.append({"id": str(s.id), "type": "space_created", "label": "Space created",
                     "user": who(s.user_id), "project": None,
                     "text": f"Space '{s.name}' created", "time": s.created_at})
    for p in sorted(db.query(Project).all(), key=lambda x: x.created_at or datetime.min, reverse=True)[:5]:
        pname, owner = proj(p.id)
        feed.append({"id": str(p.id), "type": "project_created", "label": "Project created",
                     "user": owner, "project": pname,
                     "text": f"Project '{p.name}' created", "time": p.created_at})
    for d in sorted(db.query(Document).all(), key=lambda x: x.created_at or datetime.min, reverse=True)[:5]:
        pname, owner = proj(d.project_id)
        kind = "document_processed" if d.status in ("ready", "failed") else "material_uploaded"
        feed.append({"id": str(d.id), "type": kind,
                     "label": "Document processed" if kind == "document_processed" else "Material uploaded",
                     "user": owner, "project": pname,
                     "text": f"'{d.file_name}' ({d.status})", "time": d.created_at})
    sessions = {s.id: s.project_id for s in db.query(ChatSession).all()}
    for m in sorted(db.query(Message).filter(Message.role == "user").all(),
                    key=lambda x: x.created_at or datetime.min, reverse=True)[:5]:
        pid = sessions.get(m.chat_session_id)
        pname, owner = proj(pid) if pid else (None, None)
        feed.append({"id": str(m.id), "type": "tutor_interaction", "label": "Tutor interaction",
                     "user": owner, "project": pname,
                     "text": (m.content or "")[:100], "time": m.created_at})
    for q in sorted(db.query(Quiz).filter(Quiz.status == "completed").all(),
                    key=lambda x: x.created_at or datetime.min, reverse=True)[:5]:
        pname, owner = proj(q.project_id)
        feed.append({"id": str(q.id), "type": "quiz_completed", "label": "Quiz completed",
                     "user": owner, "project": pname,
                     "text": f"Quiz '{q.name}' completed", "time": q.created_at})
    for sub in sorted(db.query(AssignmentSubmission).all(),
                      key=lambda x: x.submitted_at or datetime.min, reverse=True)[:4]:
        a = db.query(Assignment).filter(Assignment.id == sub.assignment_id).first()
        pname, owner = proj(a.project_id) if a else (None, None)
        feed.append({"id": str(sub.id), "type": "assessment_completed", "label": "Assessment completed",
                     "user": owner, "project": pname,
                     "text": f"Assignment '{a.title if a else '?'}' submitted", "time": sub.submitted_at})
    for h in sorted(db.query(MasteryHistory).order_by(MasteryHistory.created_at.desc()).limit(5).all(),
                    key=lambda x: x.created_at or datetime.min, reverse=True):
        feed.append({"id": str(h.id), "type": "mastery_updated", "label": "Mastery updated",
                     "user": who(h.user_id), "project": (project_by_id.get(h.project_id).name if project_by_id.get(h.project_id) else None),
                     "text": f"Mastery → {round(h.mastery or 0, 1)}%", "time": h.created_at})
    feed = [e for e in feed if e["time"] is not None]
    feed.sort(key=lambda e: e["time"], reverse=True)
    return feed[:limit]


@router.get("/admin/users", response_model=PageOut)
def admin_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=15, ge=1, le=MAX_PAGE_SIZE, description="Rows per page"),
    q: Optional[str] = Query(default=None, description="Substring match on name or email"),
    role: Optional[str] = Query(default=None, description="Filter by role ('user' | 'admin')"),
):
    query = db.query(User).order_by(User.created_at.desc())
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(User.email.ilike(like), User.name.ilike(like)))
    if role and role != "all":
        query = query.filter(User.role == role)
    rows, total, page, page_size = paginate_query(query, page, page_size)
    _, _, _, project_user = _maps(db)
    out = []
    for u in rows:
        spaces = db.query(Space).filter(Space.user_id == u.id).all()
        project_count = db.query(Project).filter(Project.space_id.in_([s.id for s in spaces])).count() if spaces else 0
        out.append({
            "id": u.id, "name": _display_name(u), "email": u.email,
            "role": u.role, "is_active": u.is_active,
            "spaces": len(spaces), "projects": project_count,
            "last_active": _user_last_active(db, u.id, project_user),
            "created_at": u.created_at,
        })
    return page_envelope(out, total, page, page_size)


@router.get("/admin/users/{user_id}")
def admin_user_detail(user_id: UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    users, space_by_id, project_by_id, project_user = _maps(db)
    spaces = db.query(Space).filter(Space.user_id == u.id).order_by(Space.created_at).all()
    space_ids = [s.id for s in spaces]
    projects = (
        db.query(Project).filter(Project.space_id.in_(space_ids)).order_by(Project.created_at).all()
        if space_ids else []
    )
    project_ids = [p.id for p in projects]
    concepts = db.query(Concept).filter(Concept.project_id.in_(project_ids)).all() if project_ids else []
    masteries = [c.mastery_level or 0 for c in concepts]
    quizzes = db.query(Quiz).filter(Quiz.project_id.in_(project_ids)).order_by(Quiz.created_at.desc()).all() if project_ids else []
    quiz_details = []
    for q in quizzes[:20]:
        questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == q.id).all()
        scores = [(x.evaluation or {}).get("score") for x in questions if x.user_answer is not None]
        scores = [s for s in scores if isinstance(s, (int, float))]
        quiz_details.append({
            "id": q.id, "name": q.name, "status": q.status,
            "project": project_by_id.get(q.project_id).name if project_by_id.get(q.project_id) else None,
            "average": round(sum(scores) / len(scores), 1) if scores else None,
            "questions": len(questions),
            "created_at": q.created_at,
        })
    sessions = db.query(ChatSession).filter(ChatSession.project_id.in_(project_ids)).all() if project_ids else []
    session_ids = [s.id for s in sessions]
    messages = db.query(Message).filter(Message.chat_session_id.in_(session_ids)).all() if session_ids else []
    subs = (
        db.query(AssignmentSubmission)
        .filter(AssignmentSubmission.assignment_id.in_(
            [a.id for a in db.query(Assignment).filter(Assignment.project_id.in_(project_ids)).all()]
        )).all() if project_ids else []
    )
    weak = sorted([c for c in concepts if (c.mastery_level or 0) < 40],
                  key=lambda c: c.mastery_level or 0)[:5]
    return {
        "id": u.id, "name": _display_name(u), "email": u.email, "role": u.role,
        "is_active": u.is_active, "created_at": u.created_at,
        "last_active": _user_last_active(db, u.id, project_user),
        "spaces": [{"id": s.id, "name": s.name,
                    "projects": sum(1 for p in projects if p.space_id == s.id),
                    "created_at": s.created_at} for s in spaces],
        "projects": [{"id": p.id, "name": p.name,
                      "space": space_by_id.get(p.space_id).name if space_by_id.get(p.space_id) else None,
                      "progress": _project_progress(db, p.id),
                      "last_active": _project_last_active(db, p.id),
                      "created_at": p.created_at} for p in projects],
        "learning": {
            "tutorMessages": len(messages),
            "quizzes": len(quizzes),
            "assignmentsSubmitted": len(subs),
            "concepts": len(concepts),
            "averageMastery": round(sum(masteries) / len(masteries), 1) if masteries else 0,
            "distribution": {
                "strong": sum(1 for m in masteries if m >= 70),
                "learning": sum(1 for m in masteries if 40 <= m < 70),
                "needsWork": sum(1 for m in masteries if m < 40),
            },
            "needsAttention": [{"id": c.id, "name": c.name,
                                "mastery": round(c.mastery_level or 0, 1),
                                "project": project_by_id.get(c.project_id).name if project_by_id.get(c.project_id) else None}
                               for c in weak],
        },
        "quizzes": quiz_details,
        "aiUsage": {
            "tutorMessages": len(messages),
            "userMessages": sum(1 for m in messages if m.role == "user"),
            "assistantMessages": sum(1 for m in messages if m.role == "assistant"),
        },
    }


@router.get("/admin/spaces", response_model=PageOut)
def admin_spaces(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=15, ge=1, le=MAX_PAGE_SIZE, description="Rows per page"),
    q: Optional[str] = Query(default=None, description="Substring match on space or owner"),
):
    users, _, _, _ = _maps(db)
    query = db.query(Space).order_by(Space.created_at.desc())
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.outerjoin(User, User.id == Space.user_id).filter(
            or_(Space.name.ilike(like), User.email.ilike(like), User.name.ilike(like)))
    rows, total, page, page_size = paginate_query(query, page, page_size)
    out = []
    for s in rows:
        projects = db.query(Project).filter(Project.space_id == s.id).all()
        pids = [p.id for p in projects]
        activity = len(projects)
        last = s.created_at
        if pids:
            docs = db.query(Document).filter(Document.project_id.in_(pids)).all()
            quizzes = db.query(Quiz).filter(Quiz.project_id.in_(pids)).all()
            activity += len(docs) + len(quizzes)
            stamps = [d.created_at for d in docs] + [q.created_at for q in quizzes]
            stamps = [t for t in stamps if t]
            if stamps:
                last = max([last] + stamps) if last else max(stamps)
        owner = users.get(s.user_id)
        out.append({
            "id": s.id, "name": s.name,
            "owner": owner.email if owner else None,
            "owner_name": _display_name(owner) if owner else None,
            "projects": len(projects), "activity": activity,
            "last_activity": last, "created_at": s.created_at,
        })
    return page_envelope(out, total, page, page_size)


@router.get("/admin/projects", response_model=PageOut)
def admin_projects(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=15, ge=1, le=MAX_PAGE_SIZE, description="Rows per page"),
    q: Optional[str] = Query(default=None, description="Substring match on project, space or owner"),
):
    users, space_by_id, _, project_user = _maps(db)
    query = db.query(Project).order_by(Project.created_at.desc())
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = (query.outerjoin(Space, Space.id == Project.space_id)
                 .outerjoin(User, User.id == Space.user_id)
                 .filter(or_(Project.name.ilike(like), Space.name.ilike(like),
                              User.email.ilike(like), User.name.ilike(like))))
    rows, total, page, page_size = paginate_query(query, page, page_size)
    out = []
    for p in rows:
        s = space_by_id.get(p.space_id)
        owner = users.get(project_user.get(p.id))
        docs = db.query(Document).filter(Document.project_id == p.id).count()
        quizzes = db.query(Quiz).filter(Quiz.project_id == p.id).count()
        sessions = db.query(ChatSession).filter(ChatSession.project_id == p.id).count()
        out.append({
            "id": p.id, "name": p.name,
            "space": s.name if s else None, "space_id": p.space_id,
            "owner": owner.email if owner else None,
            "owner_name": _display_name(owner) if owner else None,
            "progress": _project_progress(db, p.id),
            "activity": {"documents": docs, "quizzes": quizzes, "sessions": sessions},
            "last_active": _project_last_active(db, p.id),
            "created_at": p.created_at,
        })
    return page_envelope(out, total, page, page_size)


@router.get("/admin/activity")
def admin_activity(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    type: Optional[str] = Query(default=None, description="Filter by activity type"),
    user: Optional[str] = Query(default=None, description="Filter by user email substring"),
    project: Optional[str] = Query(default=None, description="Filter by project id"),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=100),
    page: int = Query(default=1, ge=1, description="1-based page number"),
):
    users, space_by_id, project_by_id, project_user = _maps(db)
    feed = _recent_activity(db, users, space_by_id, project_by_id, project_user, limit=500)
    types = sorted({e["type"] for e in feed})
    cutoff = datetime.utcnow() - timedelta(days=days)
    feed = [e for e in feed if e["time"] and e["time"] >= cutoff]
    if type:
        feed = [e for e in feed if e["type"] == type]
    if user:
        needle = user.lower()
        feed = [e for e in feed if e["user"] and needle in e["user"].lower()]
    if project:
        try:
            pid = UUID(project)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid project id")
        pname = project_by_id.get(pid).name if project_by_id.get(pid) else None
        feed = [e for e in feed if e["project"] == pname]
    items, total, page, page_size = paginate_list(feed, page, limit)
    return {"types": types, "items": items,
            "total": total, "page": page, "page_size": page_size,
            "pages": ceil(total / page_size) if total else 0}


@router.get("/admin/learning")
def admin_learning(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    _, space_by_id, project_by_id, _ = _maps(db)
    concepts = db.query(Concept).all()
    masteries = [c.mastery_level or 0 for c in concepts]
    quizzes = db.query(Quiz).all()
    quiz_trend = []
    for q in sorted([x for x in quizzes if x.status == "completed"],
                    key=lambda x: x.created_at or datetime.min)[-12:]:
        questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == q.id).all()
        scores = [(x.evaluation or {}).get("score") for x in questions if x.user_answer is not None]
        scores = [s for s in scores if isinstance(s, (int, float))]
        p = project_by_id.get(q.project_id)
        quiz_trend.append({
            "date": q.created_at.date().isoformat() if q.created_at else None,
            "score": round(sum(scores) / len(scores), 1) if scores else None,
            "name": q.name, "project": p.name if p else None,
        })
    history = db.query(QuizHistory).order_by(QuizHistory.created_at.desc()).limit(200).all()
    by_day = defaultdict(lambda: {"correct": 0, "total": 0})
    for h in history:
        if h.created_at:
            key = h.created_at.date().isoformat()
            by_day[key]["total"] += 1
            if h.is_correct:
                by_day[key]["correct"] += 1
    assessment_trend = [
        {"date": day, "score": round(v["correct"] / v["total"] * 100, 1)}
        for day, v in sorted(by_day.items())
    ][-14:]
    weak = sorted([c for c in concepts if (c.mastery_level or 0) < 40],
                  key=lambda c: c.mastery_level or 0)[:10]
    subs = db.query(AssignmentSubmission).all()
    submitted_scores = [round(s.score / s.total * 100, 1) for s in subs if s.total]
    return {
        "quiz": {"completed": sum(1 for q in quizzes if q.status == "completed"),
                 "trend": quiz_trend},
        "assessment": {"submitted": len(subs),
                       "averageScore": round(sum(submitted_scores) / len(submitted_scores), 1) if submitted_scores else 0,
                       "trend": assessment_trend},
        "mastery": {"average": round(sum(masteries) / len(masteries), 1) if masteries else 0,
                    "distribution": {
                        "strong": sum(1 for m in masteries if m >= 70),
                        "learning": sum(1 for m in masteries if 40 <= m < 70),
                        "needsWork": sum(1 for m in masteries if m < 40)}},
        "needsAttention": [{"id": c.id, "name": c.name,
                            "mastery": round(c.mastery_level or 0, 1),
                            "project": project_by_id.get(c.project_id).name if project_by_id.get(c.project_id) else None,
                            "space": (space_by_id.get(project_by_id.get(c.project_id).space_id).name
                                      if project_by_id.get(c.project_id) and space_by_id.get(project_by_id.get(c.project_id).space_id) else None)}
                           for c in weak],
        "recommendations": {"tracked": False,
                            "message": "Recommendations are generated inline and are not logged yet. No recommendation activity has been collected."},
    }


@router.get("/admin/jobs")
def admin_jobs(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE, description="Rows per page"),
):
    """Background work is tracked via status strings on documents/quizzes/
    assignments (no jobs table exists), so active + recent work is derived
    from non-terminal statuses. terminal=False marks still-running work."""
    jobs = []
    by_user_space = {}
    for s in db.query(Space).all():
        by_user_space[s.id] = s.user_id
    users = {u.id: u.email for u in db.query(User).all()}
    projects = {p.id: p for p in db.query(Project).all()}

    def owner_of(project_id):
        p = projects.get(project_id)
        return users.get(by_user_space.get(p.space_id)) if p else None

    queued = processing = completed = failed = 0
    for d in db.query(Document).order_by(Document.created_at.desc()).limit(30):
        terminal = d.status in ("ready", "failed")
        if d.status in ("queued",):
            queued += 1
        elif d.status in ("processing",):
            processing += 1
        elif d.status == "failed":
            failed += 1
        else:
            completed += 1
        jobs.append({"id": d.id, "name": f"Ingest '{d.file_name}'", "type": "document",
                     "status": d.status, "terminal": terminal,
                     "user": owner_of(d.project_id), "started": d.created_at})
    for q in db.query(Quiz).order_by(Quiz.created_at.desc()).limit(30):
        terminal = q.status in ("completed", "failed")
        if q.status in ("generating", "in_progress", "evaluating"):
            processing += 1
        elif q.status == "failed":
            failed += 1
        else:
            completed += 1
        jobs.append({"id": q.id, "name": f"Quiz '{q.name}'", "type": "quiz",
                     "status": q.status, "terminal": terminal,
                     "user": owner_of(q.project_id), "started": q.created_at})
    for a in db.query(Assignment).order_by(Assignment.created_at.desc()).limit(30):
        terminal = a.status in ("submitted", "failed")
        if a.status in ("draft", "ready", "generating"):
            processing += 1
        elif a.status == "failed":
            failed += 1
        else:
            completed += 1
        jobs.append({"id": a.id, "name": f"Assignment '{a.title}'", "type": "assignment",
                     "status": a.status, "terminal": terminal,
                     "user": owner_of(a.project_id), "started": a.created_at})
    jobs.sort(key=lambda j: j["started"] or datetime.min, reverse=True)
    items, total, page, page_size = paginate_list(jobs, page, page_size)
    return {"summary": {"queued": queued, "processing": processing,
                        "completed": completed, "failed": failed},
            "items": items, "total": total, "page": page,
            "page_size": page_size,
            "pages": ceil(total / page_size) if total else 0}


@router.get("/admin/evaluations")
def admin_evaluations(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=0, le=3650, description="Last N days; 0 = all time"),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE, description="Rows per page"),
):
    """AI quality dashboard: tutor groundedness · retrieval · assessment · recommendations.

    All numbers are derived from stored rows — nothing is fabricated:
    - Tutor quality comes from assistant Message.citations (cited = supported).
      Claim-level groundedness judging is not instrumented yet, so
      supportedRate == citationCoverage by construction.
    - Retrieval grounding uses assistant-message citation presence
      (zero-context = answers with 0 citations) plus measured AIUsage
      tutor_answer rows per model (calls / tokens / latency). Per-call chunk
      counts and vector distances are not logged, so those components were
      removed instead of showing permanent '—'.
    - Assessment MCQ/open stats come from QuizQuestion.evaluation scores;
      verdict pass/fail counts QuizHistory.is_correct plus evaluated quiz
      questions (score >= 60 = pass). Partial = open answers with
      0 < score < 100. Difficulty labels are not stored on questions, so the
      Accuracy-by-difficulty component was removed instead of staying empty.
    - Recommendations are generated inline and not logged with statuses;
      only measured generation count (Total) is shown. Status breakdown was
      removed instead of showing permanent zeros.
    - days=0 means all time; otherwise UTC cutoff = now - days.
    """
    cutoff = None if not days else (datetime.utcnow() - timedelta(days=days))

    def _in_range(ts):
        return True if cutoff is None else (ts is not None and ts >= cutoff)

    # ---- Tutor quality (assistant messages) ----
    assistant_msgs = db.query(Message).filter(Message.role == "assistant").all()
    assistant_msgs = [m for m in assistant_msgs if _in_range(m.created_at)]
    answers = len(assistant_msgs)
    cited_counts = []
    for m in assistant_msgs:
        c = m.citations if isinstance(m.citations, list) else []
        cited_counts.append(len(c))
    supported = sum(1 for n in cited_counts if n > 0)
    unsupported = answers - supported
    supported_rate = round(supported / answers * 100, 1) if answers else 0.0
    citation_coverage = round(supported / answers * 100, 1) if answers else 0.0
    avg_citations = round(sum(cited_counts) / answers, 2) if answers else 0.0

    # Supported rate by week (last 8 full weeks + current, Monday buckets).
    by_week: dict = {}
    for m, n in zip(assistant_msgs, cited_counts):
        if not m.created_at:
            continue
        d = m.created_at.date()
        monday = (d - timedelta(days=d.weekday())).isoformat()
        b = by_week.setdefault(monday, {"answers": 0, "supported": 0})
        b["answers"] += 1
        if n > 0:
            b["supported"] += 1
    supported_by_week = [
        {"week": w,
         "answers": v["answers"],
         "supported": v["supported"],
         "rate": round(v["supported"] / v["answers"] * 100, 1) if v["answers"] else 0.0}
        for w, v in sorted(by_week.items())
    ][-8:]

    # ---- Retrieval grounding (only measured signals) ----
    tutor_calls = answers
    zero_context_rate = round(unsupported / answers * 100, 1) if answers else 0.0
    try:
        from app.services.ai_usage_service import _resolve_provider as _resolve_eval_provider
    except Exception:
        def _resolve_eval_provider(p, m):
            return (p or "none")
    usage_rows = db.query(AIUsage).all()
    usage_in_range = [r for r in usage_rows if _in_range(r.created_at)]
    tutor_usage = [r for r in usage_in_range if (r.feature or "") == "tutor_answer"]
    by_model_map: dict = defaultdict(lambda: {"calls": 0, "tokens": 0, "lat": []})
    for r in tutor_usage:
        model = r.model or "—"
        b = by_model_map[model]
        b["calls"] += r.calls or 1
        b["tokens"] += r.total_tokens or 0
        if r.latency_ms is not None:
            b["lat"].append(r.latency_ms)
    retrieval_by_model = [
        {"model": m, "calls": v["calls"], "tokens": v["tokens"],
         "avgMs": round(sum(v["lat"]) / len(v["lat"]), 1) if v["lat"] else None}
        for m, v in sorted(by_model_map.items(), key=lambda kv: kv[1]["calls"], reverse=True)
    ]

    # ---- Assessment quality ----
    questions = db.query(QuizQuestion).all()
    questions = [q for q in questions if _in_range(q.created_at)]
    mcq_answered = [q for q in questions
                    if (q.question_type or "").lower().startswith(("multiple", "mcq"))
                    and q.user_answer is not None]
    mcq_scores = [float((q.evaluation or {}).get("score"))
                  for q in mcq_answered
                  if isinstance((q.evaluation or {}).get("score"), (int, float))]
    open_graded = [q for q in questions
                   if (q.question_type or "").lower().startswith(("open",))
                   and isinstance((q.evaluation or {}).get("score"), (int, float))]
    open_scores = [float((q.evaluation or {}).get("score")) for q in open_graded]
    partial = sum(1 for s in open_scores if 0 < s < 100)

    hist = db.query(QuizHistory).all()
    hist = [h for h in hist if _in_range(h.created_at)]
    # Verdicts: adaptive-flow QuizHistory.is_correct plus evaluated batch-quiz
    # questions (score >= 60 = pass). QuizHistory alone is empty when only the
    # batch quiz flow has been used, which left these cards at 0.
    graded_scores = [float((q.evaluation or {}).get("score")) for q in questions
                     if isinstance((q.evaluation or {}).get("score"), (int, float))]
    verdict_pass = (sum(1 for h in hist if h.is_correct)
                    + sum(1 for s in graded_scores if s >= 60))
    verdict_fail = (sum(1 for h in hist if not h.is_correct)
                    + sum(1 for s in graded_scores if s < 60))

    # ---- Recommendations: only measured generation count ----
    rec_usage = [r for r in usage_in_range if (r.feature or "") == "recommendations"]
    rec_total = sum(r.calls or 1 for r in rec_usage)

    # ---- Recent items (paginated) ----
    recent_hist = sorted(hist, key=lambda h: h.created_at or datetime.min, reverse=True)
    concepts = {c.id: c.name for c in db.query(Concept).all()}
    users = {u.id: u.email for u in db.query(User).all()}
    all_items = [{
        "id": h.id, "user": users.get(h.user_id),
        "concept": concepts.get(h.concept_id, "Unknown"),
        "question_type": h.question_type,
        "is_correct": h.is_correct, "feedback": h.evaluator_feedback,
        "created_at": h.created_at,
    } for h in recent_hist]
    items, total_items, page, page_size = paginate_list(all_items, page, page_size)
    correct_all = sum(1 for i in all_items if i["is_correct"])

    tracked = bool(answers or questions or hist or usage_in_range)
    return {
        "tracked": tracked,
        "range": {"days": days,
                  "from": cutoff.isoformat() if cutoff else None,
                  "to": datetime.utcnow().isoformat()},
        # Back-compat keys for the previous minimal UI (computed over all in-range items).
        "correctRate": round(correct_all / total_items * 100, 1) if total_items else 0,
        "evaluated": total_items,
        "items": items,
        "total": total_items, "page": page, "page_size": page_size,
        "pages": ceil(total_items / page_size) if total_items else 0,
        "tutor": {
            "answers": answers,
            "supported": supported,
            "unsupported": unsupported,
            "supportedRate": supported_rate,
            "citationCoverage": citation_coverage,
            "avgCitations": avg_citations,
            "supportedByWeek": supported_by_week,
            "note": "Supported = assistant answers with >=1 citation. Claim-level judging not instrumented yet.",
        },
        "retrieval": {
            "tutorCalls": tutor_calls,
            "zeroContextRate": zero_context_rate,
            "byModel": retrieval_by_model,
            "note": "Zero-context = assistant answers with 0 citations. Per-model calls/tokens/latency are measured AIUsage rows.",
        },
        "assessment": {
            "mcqAttempts": len(mcq_answered),
            "mcqAvgScore": round(sum(mcq_scores) / len(mcq_scores), 2) if mcq_scores else 0.0,
            "openEndedGrades": len(open_graded),
            "openEndedAvg": round(sum(open_scores) / len(open_scores), 2) if open_scores else 0.0,
            "verdictPass": verdict_pass,
            "verdictFail": verdict_fail,
            "verdictPartial": partial,
        },
        "recommendations": {
            "tracked": bool(rec_total),
            "total": rec_total,
            "message": "Recommendations are generated inline; Total counts measured recommendation generations.",
        },
    }


@router.get("/admin/ai-usage")
def admin_ai_usage(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    feature: Optional[str] = Query(default=None, description="Substring filter on feature name"),
    provider: Optional[str] = Query(default=None, description="Exact provider filter ('inception', 'groq', 'none', ...)"),
    days: int = Query(default=30, ge=1, le=365),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE, description="Rows per page"),
):
    """Screenshot-style usage: totals + feature × provider × model × day table.

    Dates are UTC calendar days from each row's created_at. Latency p50/p95
    use nearest-rank over whole-operation latencies. Cost is estimated from
    provider token counts (see ai_usage_service.estimate_cost).
    """
    def _pct(sorted_vals, p):
        if not sorted_vals:
            return None
        k = max(0, min(len(sorted_vals) - 1, int(-(-p * len(sorted_vals) // 1) - 1)))
        return sorted_vals[k]

    messages = db.query(Message).all()
    rows = db.query(AIUsage).all()
    # Resolve legacy rows stored with provider='none' (e.g. tutor fast-paths)
    # so the table never shows a blank/missing provider name. New rows are
    # already normalized at write time — this only backfills reads.
    try:
        from app.services.ai_usage_service import _resolve_provider as _resolve_usage_provider
    except Exception:
        def _resolve_usage_provider(p, m):  # fallback when metering module unavailable
            return (p or "none")

    def _prov(r):
        return _resolve_usage_provider(getattr(r, "provider", None), getattr(r, "model", None))

    if not rows:
        assistant = sum(1 for m in messages if m.role == "assistant")
        return {"tracked": False,
                "message": "AI operation tracking just started — no timed AI calls have been recorded yet. Counts below are derived from stored data.",
                "calls": 0, "tokens": 0, "cost": 0.0, "errorRate": None,
                "latencyP50": None, "latencyP95": None,
                "providers": [],
                "groups": [],
                "totals": {"interactions": assistant + db.query(Quiz).count() + db.query(Assignment).count(),
                           "tutorMessages": len(messages)},
                "byFeature": [
                    {"feature": "AI Tutor", "interactions": len(messages)},
                    {"feature": "RAG", "interactions": assistant},
                    {"feature": "Quiz generation", "interactions": db.query(Quiz).count()},
                    {"feature": "Assessment", "interactions": db.query(Assignment).count()},
                    {"feature": "Concepts", "interactions": db.query(Concept).count()},
                    {"feature": "Summarization", "interactions": 0},
                ]}

    providers = sorted({_prov(r) for r in rows})
    cutoff = datetime.utcnow() - timedelta(days=days)
    filt = [r for r in rows if r.created_at and r.created_at >= cutoff]
    if feature:
        needle = feature.strip().lower()
        filt = [r for r in filt if needle in (r.feature or "").lower()]
    if provider and provider != "all":
        filt = [r for r in filt if _prov(r) == provider]

    calls = sum(r.calls or 1 for r in filt)
    tokens = sum(r.total_tokens or 0 for r in filt)
    cost = round(sum(r.cost_usd or 0.0 for r in filt), 6)
    error_rate = round(sum(1 for r in filt if not r.success) / len(filt) * 100, 1) if filt else 0.0
    lats = sorted(r.latency_ms for r in filt if r.latency_ms is not None)
    p50 = round(_pct(lats, 0.50), 1) if lats else None
    p95 = round(_pct(lats, 0.95), 1) if lats else None

    grouped = defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0.0, "lat": []})
    for r in filt:
        key = ((r.created_at.date().isoformat() if r.created_at else "—"),
               r.feature or "unknown", _prov(r), r.model or "—")
        g = grouped[key]
        g["calls"] += r.calls or 1
        g["tokens"] += r.total_tokens or 0
        g["cost"] += r.cost_usd or 0.0
        if r.latency_ms is not None:
            g["lat"].append(r.latency_ms)
    groups = [{"day": k[0], "feature": k[1], "provider": k[2], "model": k[3],
               "calls": v["calls"], "tokens": v["tokens"],
               "cost": round(v["cost"], 6),
               "avgMs": round(sum(v["lat"]) / len(v["lat"]), 1) if v["lat"] else None}
              for k, v in grouped.items()]
    groups.sort(key=lambda g: g["day"], reverse=True)
    page_items, groups_total, page, page_size = paginate_list(groups, page, page_size)

    feats = defaultdict(int)
    for r in filt:
        feats[r.feature or "unknown"] += r.calls or 1

    return {"tracked": True,
            "message": "Measured per AI operation. Cost is estimated from provider token counts.",
            "calls": calls, "tokens": tokens, "cost": cost,
            "errorRate": error_rate, "latencyP50": p50, "latencyP95": p95,
            "providers": providers,
            "groups": page_items,
            "total": groups_total, "page": page, "page_size": page_size,
            "pages": ceil(groups_total / page_size) if groups_total else 0,
            "totals": {"interactions": calls, "tutorMessages": len(messages)},
            "byFeature": [{"feature": f, "interactions": v}
                          for f, v in sorted(feats.items())]}


@router.get("/admin/health")
def admin_health(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database = {"name": "PostgreSQL", "status": "healthy", "detail": "SELECT 1 ok"}
    except Exception as e:
        from app.utils.user_errors import short_admin_detail

        database = {"name": "PostgreSQL", "status": "unavailable", "detail": short_admin_detail(e)}
    redis = _check_redis()
    workers = _check_workers()
    providers = _ai_providers()
    docs = db.query(Document).all()
    failed = sum(1 for d in docs if d.status == "failed")
    processing = sum(1 for d in docs if d.status in ("queued", "processing"))
    return {"components": [
        {"name": "FastAPI backend", "status": "healthy", "detail": "serving this response"},
        {"name": database["name"], "status": database["status"], "detail": database["detail"]},
        {"name": "Redis", "status": redis["status"], "detail": redis["detail"]},
        {"name": "Background workers", "status": workers["status"], "detail": workers["detail"]},
        {"name": "AI provider (Inception)", "status": providers["inception"]["status"], "detail": providers["inception"]["detail"]},
        {"name": "AI provider (Groq)", "status": providers["groq"]["status"], "detail": providers["groq"]["detail"]},
        {"name": "AI provider (Google)", "status": providers["google"]["status"], "detail": providers["google"]["detail"]},
        {"name": "Document processing", "status": "degraded" if failed else "healthy",
         "detail": f"{processing} queued/processing · {failed} failed"},
    ]}
