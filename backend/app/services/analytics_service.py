"""Learning-growth computation over MasteryHistory rows.

Growth = change in estimated mastery, expressed in percentage points (pts),
never as a percent-of-percent. All functions below are pure (plain data in,
plain data out) so they are unit-testable without a database.
"""
from datetime import datetime

from loguru import logger
from sqlalchemy.exc import IntegrityError

from app.db.models.mastery import MasteryHistory

# Trend config: change (pts) within +- threshold is Stable.
TREND_THRESHOLD_PTS = 5.0
# Recent window: trend/recent-growth use the last N observations.
RECENT_WINDOW = 4
# Cap history points returned for charts.
MAX_HISTORY_POINTS = 60


def trend_for(change_pts):
    """Map a point change to a product trend state."""
    if change_pts is None:
        return "insufficient"
    if change_pts > TREND_THRESHOLD_PTS:
        return "improving"
    if change_pts < -TREND_THRESHOLD_PTS:
        return "attention"
    return "stable"


def concept_growth(points, current_mastery):
    """Growth for one concept.

    points: list of (created_at, mastery) tuples, any order.
    Returns dict with initial/current/growth/recent_growth/trend/history.
    Single-point (or empty) history -> growth None, trend "insufficient".
    """
    ordered = sorted(points or [], key=lambda p: p[0] or datetime.min)
    current = round(float(current_mastery or 0), 1)
    if not ordered:
        return {
            "initial": None, "current": current,
            "growth": None, "recent_growth": None,
            "trend": "insufficient", "history": [],
        }
    initial = round(float(ordered[0][1]), 1)
    if len(ordered) < 2:
        # A single measurement is not growth — display "—".
        growth = None
        recent = None
        trend = "insufficient"
    else:
        growth = round(current - initial, 1)
        window = ordered[-RECENT_WINDOW:]
        if len(window) < 2:
            recent = None
            trend = "insufficient"
        else:
            recent = round(current - float(window[0][1]), 1)
            trend = trend_for(recent)
    history = [
        {"date": (dt.date().isoformat() if dt else None), "mastery": round(float(m), 1)}
        for dt, m in ordered[-MAX_HISTORY_POINTS:]
    ]
    return {
        "initial": initial, "current": current,
        "growth": growth, "recent_growth": recent,
        "trend": trend, "history": history,
    }


def project_growth(entries):
    """Project-level growth from per-concept growth entries.

    Only concepts WITH history participate (both baseline and current must
    be real measurements). Returns None when no concept has history.
    """
    usable = [e for e in entries if e.get("growth") is not None]
    if not usable:
        return {"initial": None, "current": None, "growth": None, "trend": "insufficient"}
    initial = round(sum(e["initial"] for e in usable) / len(usable), 1)
    current = round(sum(e["current"] for e in usable) / len(usable), 1)
    growth = round(current - initial, 1)
    return {"initial": initial, "current": current, "growth": growth, "trend": trend_for(growth)}


def project_series(concept_points):
    """Carry-forward average-mastery series across concepts.

    concept_points: {concept_id: [(created_at, mastery), ...]}.
    At each distinct event time, value = average of every concept's latest
    known mastery at that time. Returns [{date, mastery}] capped by
    MAX_HISTORY_POINTS. Honest step series — no interpolation invented.
    """
    per_concept = {
        cid: sorted(pts, key=lambda p: p[0] or datetime.min)
        for cid, pts in (concept_points or {}).items() if pts
    }
    if not per_concept:
        return []
    times = sorted({dt for pts in per_concept.values() for dt, _ in pts if dt})
    times = times[-MAX_HISTORY_POINTS:]
    series = []
    for t in times:
        vals = []
        for pts in per_concept.values():
            known = [m for dt, m in pts if dt and dt <= t]
            if known:
                vals.append(float(known[-1]))
        if vals:
            series.append({
                "date": t.date().isoformat(),
                "mastery": round(sum(vals) / len(vals), 1),
            })
    return series


def insight_text(name, growth, trend):
    """Data-grounded insight sentence. Never invents a cause."""
    if growth is None:
        return f"Not enough history yet to measure growth for {name}."
    pts = abs(growth)
    if trend == "improving":
        return (f"Mastery of {name} has increased by {pts} percentage points "
                f"since the first measurement.")
    if trend == "attention":
        return (f"Mastery of {name} has decreased by {pts} percentage points "
                f"recently. Reviewing the related materials may help.")
    return (f"Mastery of {name} has remained relatively stable "
            f"across recent assessments ({growth:+} pts overall).")


def record_mastery_snapshot(db, *, user_id, project_id, concept_id, new_mastery,
                              source, source_id=None, previous_mastery=None, baseline_at=None):
    """Append a MasteryHistory row after a real mastery update.

    On the first snapshot for a concept, a baseline row (the pre-update
    value) is inserted first so growth has an honest starting point.
    Duplicate (concept, source, source_id) inserts are swallowed
    (idempotent retries). Returns 'recorded' | 'duplicate' | 'skipped:...'.
    """
    if user_id is None or project_id is None or concept_id is None:
        return "skipped:missing-owner"
    try:
        exists = (
            db.query(MasteryHistory.id)
            .filter(MasteryHistory.concept_id == concept_id)
            .first()
        )
        if not exists:
            db.add(MasteryHistory(
                user_id=user_id, project_id=project_id, concept_id=concept_id,
                mastery=round(float(previous_mastery or 0), 1),
                source="baseline", source_id=None,
                created_at=baseline_at or datetime.utcnow(),
            ))
            db.commit()
        db.add(MasteryHistory(
            user_id=user_id, project_id=project_id, concept_id=concept_id,
            mastery=round(float(new_mastery), 1),
            source=source, source_id=source_id,
        ))
        db.commit()
        return "recorded"
    except IntegrityError:
        db.rollback()
        return "duplicate:already-recorded"
    except Exception:
        db.rollback()
        return "skipped:error"


def recompute_project_progress(db, project_id) -> float | None:
    """Refresh Project.overall_progress from live concept mastery.

    Progress = average Concept.mastery_level across the project (0.0 when the
    project has no concepts yet). Called best-effort after every mastery write
    (quiz submit, tutor chat signal) so dashboards and rollups never show a
    stale write-once value. Never raises — a progress failure must not break
    the mastery update it follows.
    """
    try:
        from app.db.models.assessment import Concept
        from app.db.models.project import Project

        project = db.get(Project, project_id)
        if project is None:
            return None
        concepts = db.query(Concept).filter(Concept.project_id == project_id).all()
        avg = round(sum(c.mastery_level or 0 for c in concepts) / len(concepts), 1) if concepts else 0.0
        project.overall_progress = avg
        db.commit()
        return avg
    except Exception as e:
        db.rollback()
        logger.warning(f"[analytics.progress] recompute skipped project={project_id}: {e}")
        return None
