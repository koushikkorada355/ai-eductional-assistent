"""Growth calculation tests (pure service functions, no DB needed).

Covers spec cases 1-7. Cases 8-9 (real assessment flow, duplicate
processing) are verified against the live stack — see docs/GROWTH.md.
"""
from datetime import datetime, timedelta

from app.services.analytics_service import (
    concept_growth, project_growth, project_series, trend_for,
)


def pts(*values, start="2026-09-01"):
    base = datetime.fromisoformat(start)
    return [(base + timedelta(days=i), v) for i, v in enumerate(values)]


def test_increasing():
    g = concept_growth(pts(40, 50, 60, 70), 70)
    assert g["current"] == 70
    assert g["growth"] == 30
    assert g["trend"] == "improving"


def test_decreasing():
    g = concept_growth(pts(70, 65, 60), 60)
    assert g["current"] == 60
    assert g["growth"] == -10
    assert g["trend"] == "attention"


def test_stable():
    g = concept_growth(pts(60, 61, 59, 60), 60)
    assert g["current"] == 60
    assert g["growth"] == 0
    assert g["trend"] == "stable"


def test_single_point_no_growth():
    # One measurement is not growth: Growth shows "—", trend needs data.
    g = concept_growth(pts(60), 60)
    assert g["current"] == 60
    assert g["growth"] is None
    assert g["recent_growth"] is None
    assert g["trend"] == "insufficient"


def test_empty_history():
    g = concept_growth([], 60)
    assert g["growth"] is None
    assert g["trend"] == "insufficient"


def test_multiple_concepts_independent():
    a = concept_growth(pts(40, 70), 70)
    b = concept_growth(pts(80, 60), 60)
    assert a["growth"] == 30 and b["growth"] == -20
    assert a["trend"] == "improving" and b["trend"] == "attention"


def test_project_isolation():
    # Growth for project A uses only A's points.
    proj = project_growth([
        {"initial": 30, "current": 70, "growth": 40},
        {"initial": 40, "current": 65, "growth": 25},
        {"initial": 50, "current": 75, "growth": 25},
    ])
    assert proj == {"initial": 40.0, "current": 70.0, "growth": 30.0, "trend": "improving"}


def test_project_no_history():
    proj = project_growth([{"initial": None, "current": 50, "growth": None}])
    assert proj["growth"] is None and proj["trend"] == "insufficient"


def test_project_series_carry_forward():
    t0 = datetime(2026, 9, 1)
    t1 = datetime(2026, 9, 5)
    series = project_series({
        "a": [(t0, 40), (t1, 70)],
        "b": [(t0, 50)],  # b stays 50 at t1 (carry-forward)
    })
    assert series == [
        {"date": "2026-09-01", "mastery": 45.0},
        {"date": "2026-09-05", "mastery": 60.0},
    ]


def test_trend_thresholds():
    assert trend_for(5.1) == "improving"
    assert trend_for(5.0) == "stable"
    assert trend_for(-5.0) == "stable"
    assert trend_for(-5.1) == "attention"
    assert trend_for(None) == "insufficient"
