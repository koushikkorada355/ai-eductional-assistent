"""Read-only analytics aggregations over existing tables.

Additive only: no schema changes, no writes, no changes to existing endpoints.
All values are derived from data the backend already stores.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_project
from app.db.models.assessment import (
    Assignment,
    AssignmentQuestion,
    AssignmentSubmission,
    Concept,
    Quiz,
    QuizQuestion,
)
from app.db.models.chat import ChatSession, Message
from app.db.models.document import Document, DocumentChunk
from app.db.models.mastery import QuizHistory, MasteryHistory
from app.db.models.project import Project
from app.db.models.space import Space
from app.db.models.user import User
from app.db.session import get_db
from app.services.analytics_service import (
    concept_growth, project_growth, project_series, insight_text,
)

router = APIRouter()


def _lvl(mastery: float) -> str:
    if mastery >= 70:
        return "strong"
    if mastery >= 40:
        return "learning"
    return "weak"


def _avg_score(questions) -> float | None:
    scores = [(q.evaluation or {}).get("score") for q in questions if q.user_answer is not None]
    scores = [s for s in scores if isinstance(s, (int, float))]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def _user_spaces(db: Session, user: User):
    return db.query(Space).filter(Space.user_id == user.id).order_by(Space.created_at).all()


def _user_projects(db: Session, user: User):
    spaces = _user_spaces(db, user)
    if not spaces:
        return [], []
    projects = (
        db.query(Project)
        .filter(Project.space_id.in_([s.id for s in spaces]))
        .order_by(Project.created_at)
        .all()
    )
    return spaces, projects


def _project_map(db: Session, projects):
    spaces = {s.id: s for s in db.query(Space).all()}
    return spaces, {p.id: p for p in projects}


def _concepts_for_projects(db: Session, project_ids):
    if not project_ids:
        return []
    return db.query(Concept).filter(Concept.project_id.in_(project_ids)).all()


def _quizzes_for_projects(db: Session, project_ids):
    if not project_ids:
        return []
    return (
        db.query(Quiz)
        .filter(Quiz.project_id.in_(project_ids))
        .order_by(Quiz.created_at.desc())
        .all()
    )


def _daily_counts(rows, days=14):
    buckets = defaultdict(int)
    for r in rows:
        key = r.created_at.date().isoformat() if r.created_at else None
        if key:
            buckets[key] += 1
    today = datetime.utcnow().date()
    return [
        {"date": (today - timedelta(days=i)).isoformat(),
         "count": buckets.get((today - timedelta(days=i)).isoformat(), 0)}
        for i in range(days - 1, -1, -1)
    ]


def _concept_payload(c: Concept, space_id=None, project_name=None):
    mastery = round(c.mastery_level or 0)
    payload = {
        "id": c.id,
        "project_id": c.project_id,
        "name": c.name,
        "description": c.description,
        "mastery": mastery,
        "level": _lvl(mastery),
        "last_assessed_at": c.last_assessed_at,
    }
    if space_id is not None:
        payload["space_id"] = space_id
    if project_name is not None:
        payload["project_name"] = project_name
    return payload


@router.get("/analytics/overview")
def analytics_overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    spaces, projects = _user_projects(db, current_user)
    space_by_id = {s.id: s for s in spaces}
    project_ids = [p.id for p in projects]

    spaces_payload = []
    for s in spaces:
        s_projects = [p for p in projects if p.space_id == s.id]
        avg = round(sum(p.overall_progress or 0 for p in s_projects) / len(s_projects), 1) if s_projects else 0
        spaces_payload.append({
            "id": s.id,
            "name": s.name,
            "progress": avg,
            "projects": [{"id": p.id, "name": p.name, "progress": round(p.overall_progress or 0, 1)} for p in s_projects],
        })

    concepts = _concepts_for_projects(db, project_ids)
    concept_payloads = [
        _concept_payload(c, space_id=space_by_id[p.space_id].id if (p := next((x for x in projects if x.id == c.project_id), None)) and p.space_id in space_by_id else None,
                         project_name=next((x.name for x in projects if x.id == c.project_id), None))
        for c in concepts
    ]
    masteries = [c["mastery"] for c in concept_payloads]
    avg_mastery = round(sum(masteries) / len(masteries), 1) if masteries else 0
    distribution = {
        "strong": sum(1 for m in masteries if m >= 70),
        "learning": sum(1 for m in masteries if 40 <= m < 70),
        "needsWork": sum(1 for m in masteries if m < 40),
    }
    needs_attention = sorted([c for c in concept_payloads if c["mastery"] < 40], key=lambda c: c["mastery"])[:5]
    strongest = sorted([c for c in concept_payloads if c["mastery"] >= 70], key=lambda c: -c["mastery"])[:5]

    # Per-project growth (single history query, grouped in Python).
    growth_by_project = {}
    if project_ids:
        all_history = (
            db.query(MasteryHistory)
            .filter(MasteryHistory.project_id.in_(project_ids))
            .order_by(MasteryHistory.created_at)
            .all()
        )
        pts_by_project_concept = {}
        for h in all_history:
            pts_by_project_concept.setdefault((h.project_id, h.concept_id), []).append((h.created_at, h.mastery))
        concept_by_id = {c.id: c for c in concepts}
        per_project_entries = {}
        for (pid, cid), pts in pts_by_project_concept.items():
            c = concept_by_id.get(cid)
            if c is None:
                continue
            per_project_entries.setdefault(pid, []).append(concept_growth(pts, c.mastery_level or 0))
        for p in projects:
            growth_by_project[str(p.id)] = project_growth(per_project_entries.get(p.id, []))

    # Per-project live mastery (from current concept levels, not the
    # write-never overall_progress column) paired with growth above.
    mastery_by_project = {}
    for p in projects:
        pcs = [c for c in concepts if c.project_id == p.id]
        avg = round(sum(c.mastery_level or 0 for c in pcs) / len(pcs), 1) if pcs else 0
        g = growth_by_project.get(str(p.id), {})
        mastery_by_project[str(p.id)] = {
            "project_id": p.id, "project_name": p.name, "space_id": p.space_id,
            "average": avg, "concepts": len(pcs),
            "growth": g.get("growth"), "trend": g.get("trend", "insufficient"),
        }

    quizzes = _quizzes_for_projects(db, project_ids)
    quiz_details = []
    for q in quizzes:
        questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == q.id).all()
        project = next((p for p in projects if p.id == q.project_id), None)
        quiz_details.append({
            "id": q.id,
            "project_id": q.project_id,
            "project_name": project.name if project else None,
            "space_id": project.space_id if project else None,
            "name": q.name,
            "status": q.status,
            "average": _avg_score(questions),
            "questions": len(questions),
            "created_at": q.created_at,
        })
    completed = [q for q in quiz_details if q["status"] == "completed" and q["average"] is not None]
    quiz_accuracy = round(sum(q["average"] for q in completed) / len(completed), 1) if completed else 0
    quiz_trend = [
        {"date": q["created_at"].date().isoformat() if q["created_at"] else None, "score": q["average"], "name": q["name"],
         "project": q["project_name"]}
        for q in sorted(completed, key=lambda q: q["created_at"] or datetime.min)[-12:]
    ]

    assignments = db.query(Assignment).filter(Assignment.project_id.in_(project_ids)).all() if project_ids else []
    submitted_scores = []
    assignment_trend = []
    for a in assignments:
        sub = (
            db.query(AssignmentSubmission)
            .filter(AssignmentSubmission.assignment_id == a.id)
            .order_by(AssignmentSubmission.submitted_at.desc())
            .first()
        )
        if sub and sub.total:
            submitted_scores.append(round(sub.score / sub.total * 100, 1))
            aproj = next((p for p in projects if p.id == a.project_id), None)
            assignment_trend.append({
                "id": a.id, "name": a.title,
                "project": aproj.name if aproj else None,
                "date": sub.submitted_at.date().isoformat() if sub.submitted_at else None,
                "score": round(sub.score / sub.total * 100, 1),
            })
    assignment_trend = sorted(assignment_trend, key=lambda e: e["date"] or "")[-12:]

    sessions = db.query(ChatSession).filter(ChatSession.project_id.in_(project_ids)).all() if project_ids else []
    session_ids = [s.id for s in sessions]
    messages = db.query(Message).filter(Message.chat_session_id.in_(session_ids)).all() if session_ids else []
    session_project = {s.id: s.project_id for s in sessions}
    tutor_by_project = defaultdict(lambda: {"total": 0, "user": 0, "assistant": 0})
    for m in messages:
        pid = session_project.get(m.chat_session_id)
        if pid is None:
            continue
        tutor_by_project[pid]["total"] += 1
        if m.role in tutor_by_project[pid]:
            tutor_by_project[pid][m.role] += 1

    documents = db.query(Document).filter(Document.project_id.in_(project_ids)).all() if project_ids else []
    docs_by_status = defaultdict(int)
    for d in documents:
        docs_by_status[d.status] += 1

    activity = []
    for q in quizzes[:5]:
        project = next((p for p in projects if p.id == q.project_id), None)
        activity.append({"id": q.id, "type": "quiz",
                         "project": project.name if project else None,
                         "text": f"Quiz '{q.name}' ({q.status})",
                         "time": q.created_at})
    for a in sorted(assignments, key=lambda x: x.created_at or datetime.min, reverse=True)[:4]:
        project = next((p for p in projects if p.id == a.project_id), None)
        activity.append({"id": a.id, "type": "assignment",
                         "project": project.name if project else None,
                         "text": f"Assignment '{a.title}' ({a.status})",
                         "time": a.created_at})
    for d in sorted(documents, key=lambda x: x.created_at or datetime.min, reverse=True)[:4]:
        project = next((p for p in projects if p.id == d.project_id), None)
        activity.append({"id": d.id, "type": "upload",
                         "project": project.name if project else None,
                         "text": f"Uploaded '{d.file_name}' ({d.status})",
                         "time": d.created_at})
    for m in sorted([m for m in messages if m.role == "user"], key=lambda x: x.created_at or datetime.min, reverse=True)[:4]:
        pid = session_project.get(m.chat_session_id)
        project = next((p for p in projects if p.id == pid), None)
        activity.append({"id": m.id, "type": "tutor",
                         "project": project.name if project else None,
                         "text": (m.content or "")[:80],
                         "time": m.created_at})
    activity = sorted(activity, key=lambda e: e["time"] or datetime.min, reverse=True)[:8]

    recommendations = []
    for c in needs_attention[:3]:
        recommendations.append({
            "title": f"Practice '{c['name']}'",
            "text": f"Mastery is {c['mastery']}% in {c.get('project_name') or 'a project'}. A quiz would help.",
            "space_id": c.get("space_id"), "project_id": c.get("project_id"),
        })
    for p in projects:
        if not any(d.project_id == p.id for d in documents):
            recommendations.append({
                "title": f"Upload materials to '{p.name}'",
                "text": "The tutor, concepts and quizzes need source documents.",
                "space_id": p.space_id, "project_id": p.id,
            })
            if len(recommendations) >= 4:
                break
    for q in quiz_details:
        if q["status"] == "failed":
            recommendations.append({
                "title": f"Retry '{q['name']}'",
                "text": "Quiz generation failed. Start a new attempt.",
                "space_id": q.get("space_id"), "project_id": q.get("project_id"),
            })
            break

    avg_progress = round(sum(p.overall_progress or 0 for p in projects) / len(projects), 1) if projects else 0
    return {
        "kpis": {
            "spaces": len(spaces),
            "projects": len(projects),
            "averageProgress": avg_progress,
            "averageMastery": avg_mastery,
            "quizAccuracy": quiz_accuracy,
            "quizzesCompleted": len(completed),
            "tutorMessages": len(messages),
            "documents": len(documents),
        },
        "spaces": spaces_payload,
        "concepts": {"average": avg_mastery, "distribution": distribution,
                     "needsAttention": needs_attention, "strongest": strongest},
        "quizzes": {"completed": len(completed), "accuracy": quiz_accuracy,
                    "trend": quiz_trend, "recent": quiz_details[:8]},
        "assignments": {"total": len(assignments),
                        "submitted": len(submitted_scores),
                        "averageScore": round(sum(submitted_scores) / len(submitted_scores), 1) if submitted_scores else 0,
                        "trend": assignment_trend},
        "tutor": {"total": len(messages),
                  "user": sum(1 for m in messages if m.role == "user"),
                  "assistant": sum(1 for m in messages if m.role == "assistant"),
                  "daily": _daily_counts(messages),
                  "byProject": [{"project_id": pid,
                                 "project_name": next((p.name for p in projects if p.id == pid), None),
                                 **counts} for pid, counts in tutor_by_project.items()]},
        "documents": {"total": len(documents), "byStatus": dict(docs_by_status)},
        "growthByProject": growth_by_project,
        "masteryByProject": mastery_by_project,
        "activity": activity,
        "recommendations": recommendations[:4],
    }


@router.get("/spaces/{space_id}/projects/{project_id}/analytics")
def project_analytics(
    space_id: UUID,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    concepts = db.query(Concept).filter(Concept.project_id == project.id).all()
    concept_payloads = [_concept_payload(c) for c in concepts]
    masteries = [c["mastery"] for c in concept_payloads]
    avg_mastery = round(sum(masteries) / len(masteries), 1) if masteries else 0

    quizzes = db.query(Quiz).filter(Quiz.project_id == project.id).order_by(Quiz.created_at.desc()).all()
    attempts = []
    for q in quizzes:
        questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == q.id).all()
        attempts.append({
            "id": q.id, "name": q.name, "status": q.status,
            "average": _avg_score(questions), "questions": len(questions),
            "created_at": q.created_at,
        })
    completed = [a for a in attempts if a["status"] == "completed" and a["average"] is not None]
    quiz_trend = [
        {"id": a["id"], "name": a["name"],
         "date": a["created_at"].date().isoformat() if a["created_at"] else None, "score": a["average"]}
        for a in sorted(completed, key=lambda a: a["created_at"] or datetime.min)[-12:]
    ]

    concept_ids = [c.id for c in concepts]
    history = (
        db.query(QuizHistory)
        .filter(QuizHistory.concept_id.in_(concept_ids))
        .order_by(QuizHistory.created_at)
        .all()
    ) if concept_ids else []
    by_day = defaultdict(lambda: {"correct": 0, "total": 0})
    for h in history:
        if h.created_at:
            key = h.created_at.date().isoformat()
            by_day[key]["total"] += 1
            if h.is_correct:
                by_day[key]["correct"] += 1
    mastery_trend = [
        {"date": day, "score": round(v["correct"] / v["total"] * 100, 1)}
        for day, v in sorted(by_day.items())
    ][-14:]
    concept_history = defaultdict(list)
    for h in sorted(history, key=lambda x: x.created_at or datetime.min, reverse=True):
        if len(concept_history[h.concept_id]) < 5:
            concept_history[h.concept_id].append({
                "is_correct": h.is_correct,
                "feedback": h.evaluator_feedback,
                "created_at": h.created_at,
            })

    sessions = db.query(ChatSession).filter(ChatSession.project_id == project.id).all()
    session_ids = [s.id for s in sessions]
    messages = db.query(Message).filter(Message.chat_session_id.in_(session_ids)).all() if session_ids else []

    assignments = db.query(Assignment).filter(Assignment.project_id == project.id).all()
    submitted_scores = []
    assignment_trend = []
    for a in assignments:
        sub = (
            db.query(AssignmentSubmission)
            .filter(AssignmentSubmission.assignment_id == a.id)
            .order_by(AssignmentSubmission.submitted_at.desc())
            .first()
        )
        if sub and sub.total:
            submitted_scores.append(round(sub.score / sub.total * 100, 1))
            assignment_trend.append({
                "id": a.id, "name": a.title,
                "date": sub.submitted_at.date().isoformat() if sub.submitted_at else None,
                "score": round(sub.score / sub.total * 100, 1),
            })
    assignment_trend = sorted(assignment_trend, key=lambda e: e["date"] or "")[-12:]

    documents = db.query(Document).filter(Document.project_id == project.id).order_by(Document.created_at.desc()).all()
    doc_stats = []
    for d in documents:
        pages, chunks = db.query(func.max(DocumentChunk.page_number), func.count(DocumentChunk.id)).filter(
            DocumentChunk.document_id == d.id).first()
        doc_stats.append({
            "id": d.id, "file_name": d.file_name, "status": d.status,
            "pages": pages or 0, "chunks": chunks or 0, "created_at": d.created_at,
        })

    recommendations = []
    # ---- Learning growth (real MasteryHistory rows, project-isolated) ----
    history_rows = (
        db.query(MasteryHistory)
        .filter(MasteryHistory.project_id == project.id)
        .order_by(MasteryHistory.created_at)
        .all()
    )
    points_by_concept = {}
    for h in history_rows:
        points_by_concept.setdefault(h.concept_id, []).append((h.created_at, h.mastery))
    growth_concepts = []
    for c in concepts:
        g = concept_growth(points_by_concept.get(c.id, []), c.mastery_level or 0)
        growth_concepts.append({
            "concept_id": c.id, "name": c.name, **g,
            "insight": insight_text(c.name, g["growth"], g["trend"]),
        })
    growth_overall = project_growth(growth_concepts)
    og, ot = growth_overall["growth"], growth_overall["trend"]
    if og is None:
        growth_overall["insight"] = "Complete assessments to start measuring growth."
    elif ot == "improving":
        growth_overall["insight"] = (f"Your overall mastery has increased by {abs(og)} "
                                     f"percentage points since the first measurement.")
    elif ot == "attention":
        growth_overall["insight"] = (f"Your overall mastery has decreased by {abs(og)} "
                                     f"percentage points recently. Reviewing weaker concepts may help.")
    else:
        growth_overall["insight"] = (f"Your overall mastery has remained relatively stable "
                                     f"({og:+} pts overall).")
    growth_payload = {
        "overall": growth_overall,
        "concepts": growth_concepts,
        "series": project_series(points_by_concept),
    }

    # Growth-driven recommendations (real trend data, no invented causes).
    growth_entries = growth_payload["concepts"]
    for g in growth_entries:
        if g["trend"] == "attention":
            recommendations.append({"title": f"Review '{g['name']}' fundamentals",
                                    "text": g["insight"]})
            break
    for g in growth_entries:
        if g["trend"] == "improving" and (g["current"] or 0) < 70:
            recommendations.append({"title": f"Continue practicing '{g['name']}'",
                                    "text": g["insight"]})
            break
    for g in growth_entries:
        if (g["current"] or 0) >= 70 and g["trend"] in ("stable", "improving"):
            recommendations.append({"title": f"'{g['name']}' is solid",
                                    "text": "This concept is strong and stable — focus your time on weaker areas."})
            break
    weak = sorted([c for c in concept_payloads if c["mastery"] < 40], key=lambda c: c["mastery"])[:3]
    for c in weak:
        recommendations.append({"title": f"Practice '{c['name']}'",
                                "text": f"Mastery is {c['mastery']}%. Generate a quiz targeting it."})
    if not documents:
        recommendations.append({"title": "Upload your first PDF",
                                "text": "Materials power concepts, tutor answers and quizzes."})
    for a in assignments:
        if a.status == "ready":
            recommendations.append({"title": f"Complete '{a.title}'",
                                    "text": "A generated assignment is waiting for your answers."})
            break

    return {
        "project": {"id": project.id, "name": project.name,
                    "progress": round(project.overall_progress or 0, 1),
                    "space_id": space_id},
        "kpis": {
            "averageMastery": avg_mastery,
            "quizAccuracy": round(sum(a["average"] for a in completed) / len(completed), 1) if completed else 0,
            "quizzesCompleted": len(completed),
            "tutorMessages": len(messages),
        },
        "concepts": concept_payloads,
        "distribution": {
            "strong": sum(1 for m in masteries if m >= 70),
            "learning": sum(1 for m in masteries if 40 <= m < 70),
            "needsWork": sum(1 for m in masteries if m < 40),
        },
        "needsAttention": sorted([c for c in concept_payloads if c["mastery"] < 40], key=lambda c: c["mastery"])[:5],
        "strongest": sorted([c for c in concept_payloads if c["mastery"] >= 70], key=lambda c: -c["mastery"])[:5],
        "conceptHistory": {str(k): v for k, v in concept_history.items()},
        "quizzes": {"attempts": attempts[:10], "trend": quiz_trend},
        "masteryTrend": mastery_trend,
        "tutor": {"total": len(messages),
                  "user": sum(1 for m in messages if m.role == "user"),
                  "assistant": sum(1 for m in messages if m.role == "assistant"),
                  "daily": _daily_counts(messages)},
        "assignments": {"total": len(assignments),
                        "submitted": len(submitted_scores),
                        "averageScore": round(sum(submitted_scores) / len(submitted_scores), 1) if submitted_scores else 0,
                        "trend": assignment_trend},
        "documents": {"total": len(documents), "items": doc_stats},
        "growth": growth_payload,
        "recommendations": recommendations[:4],
    }
