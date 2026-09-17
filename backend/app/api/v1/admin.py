"""Admin read-only endpoints for the AI Learning Operations Center.

Additive only. Every route requires role == 'admin'. No existing endpoint is
modified in a breaking way — new keys are added, existing keys are kept.

Where platform instrumentation does not exist (token usage, latency, cost,
recommendations log), endpoints report honestly instead of fabricating data.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
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
from app.db.models.project import Project
from app.db.models.space import Space
from app.db.models.user import User
from app.db.session import get_db

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
        return {"status": "unavailable", "detail": f"{type(e).__name__}: {e}"}


def _check_workers() -> dict:
    try:
        from app.tasks.celery_app import celery_app

        ping = celery_app.control.ping(timeout=2)
        if ping:
            names = sorted({k for node in ping for k in node})
            return {"status": "healthy", "detail": f"{len(ping)} worker(s): {', '.join(names)}"}
        return {"status": "degraded", "detail": "No workers replied to ping"}
    except Exception as e:
        return {"status": "degraded", "detail": f"{type(e).__name__}: {e}"}


def _ai_providers() -> dict:
    return {
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
        database = {"status": "unavailable", "detail": f"{type(e).__name__}: {e}"}
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


@router.get("/admin/users")
def admin_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    _, _, _, project_user = _maps(db)
    out = []
    for u in users:
        spaces = db.query(Space).filter(Space.user_id == u.id).all()
        project_count = db.query(Project).filter(Project.space_id.in_([s.id for s in spaces])).count() if spaces else 0
        out.append({
            "id": u.id, "name": _display_name(u), "email": u.email,
            "role": u.role, "is_active": u.is_active,
            "spaces": len(spaces), "projects": project_count,
            "last_active": _user_last_active(db, u.id, project_user),
            "created_at": u.created_at,
        })
    return out


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


@router.get("/admin/spaces")
def admin_spaces(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users, _, _, _ = _maps(db)
    out = []
    for s in db.query(Space).order_by(Space.created_at.desc()).all():
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
    return out


@router.get("/admin/projects")
def admin_projects(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users, space_by_id, _, project_user = _maps(db)
    out = []
    for p in db.query(Project).order_by(Project.created_at.desc()).all():
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
    return out


@router.get("/admin/activity")
def admin_activity(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    type: Optional[str] = Query(default=None, description="Filter by activity type"),
    user: Optional[str] = Query(default=None, description="Filter by user email substring"),
    project: Optional[str] = Query(default=None, description="Filter by project id"),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=100),
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
    return {"types": types,
            "items": feed[:limit]}


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
def admin_jobs(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
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
    return {"summary": {"queued": queued, "processing": processing,
                        "completed": completed, "failed": failed},
            "items": jobs[:50]}


@router.get("/admin/evaluations")
def admin_evaluations(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    history = db.query(QuizHistory).order_by(QuizHistory.created_at.desc()).limit(50).all()
    concepts = {c.id: c.name for c in db.query(Concept).all()}
    users = {u.id: u.email for u in db.query(User).all()}
    items = [{
        "id": h.id, "user": users.get(h.user_id),
        "concept": concepts.get(h.concept_id, "Unknown"),
        "question_type": h.question_type,
        "is_correct": h.is_correct, "feedback": h.evaluator_feedback,
        "created_at": h.created_at,
    } for h in history]
    total = len(items)
    correct = sum(1 for i in items if i["is_correct"])
    return {"tracked": total > 0,
            "correctRate": round(correct / total * 100, 1) if total else 0,
            "evaluated": total, "items": items}


@router.get("/admin/ai-usage")
def admin_ai_usage(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    messages = db.query(Message).all()
    assistant = sum(1 for m in messages if m.role == "assistant")
    # No token/cost columns exist anywhere; feature activity below is derived
    # from stored rows and reported honestly as interaction counts.
    return {"tracked": False,
            "message": "AI token usage is not instrumented yet. No token, latency, or cost data has been collected.",
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


@router.get("/admin/health")
def admin_health(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database = {"name": "PostgreSQL", "status": "healthy", "detail": "SELECT 1 ok"}
    except Exception as e:
        database = {"name": "PostgreSQL", "status": "unavailable", "detail": f"{type(e).__name__}: {e}"}
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
        {"name": "AI provider (Groq)", "status": providers["groq"]["status"], "detail": providers["groq"]["detail"]},
        {"name": "AI provider (Google)", "status": providers["google"]["status"], "detail": providers["google"]["detail"]},
        {"name": "Document processing", "status": "degraded" if failed else "healthy",
         "detail": f"{processing} queued/processing · {failed} failed"},
    ]}
