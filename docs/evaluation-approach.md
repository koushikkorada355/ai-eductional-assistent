# Evaluation Approach — How AI Behavior Is Measured

## 1. What is evaluated, and where

All metrics are derived from stored rows — nothing is fabricated. Dashboard: `GET /admin/evaluations` (`backend/app/api/v1/admin.py:603-778`); UI: Admin → AI Evaluation tab.

| Area | Metric | Source | Honest caveat (shown in UI) |
|------|--------|--------|------------------------------|
| Tutor quality | Supported rate, citation coverage, avg citations, supported-by-week | Assistant `Message.citations` (cited = supported) | Claim-level groundedness judging not instrumented; supported == citation coverage by construction |
| Retrieval grounding | Zero-context rate (answers with 0 citations), per-model calls/tokens/latency | Assistant messages + `AIUsage` rows with `feature=tutor_answer` | Per-call chunk counts / vector distances not logged |
| Assessment | MCQ attempts + avg, open-ended grades + avg, partial (0<score<100), verdict pass (score≥60) / fail | `QuizQuestion.evaluation` + `QuizHistory.is_correct` | Difficulty labels not stored; no accuracy-by-difficulty |
| Recommendations | Total measured generations (`feature=recommendations`) | `AIUsage` rows | Generated inline, not logged with statuses; `admin/learning` reports `tracked:false` |

## 2. Automated tests

- `backend/tests/test_growth.py` — 10 tests over pure growth functions (increase, decrease, stable, single-point, empty, independence, project isolation, carry-forward series, thresholds). Run: `python -m pytest backend/tests/ -q` (needs backend deps installed).
- Deliberately not unit-tested with mocks: LLM grading quality and retrieval relevance are provider-dependent and evaluated via the dashboard + seed data below instead.

## 3. Demo / regression procedure

1. Seed a deterministic 8-week demo slice (concepts, cited tutor messages, graded quiz questions, history, usage rows): `docker compose exec backend python scripts/seed_evaluation.py` (`--force` to reseed; `backend/scripts/seed_evaluation.py:1-14`).
2. Record baseline Admin → AI Evaluation numbers (supported rate, retrieval zero-context, MCQ/open avgs) at 7d / 30d / All.
3. Change prompts, models, or retrieval; re-seed with `--force` on a staging DB and compare — a drop in supported rate or a rise in zero-context rate is a regression.
4. Rule-based guardrails that backstop the LLM (blank-answer=0 in `app/tasks/quiz_tasks.py:27-47`, suggestion vocabulary/novelty gates in `app/ai/nodes/tutor_nodes.py:158-202`, concept-name validation in `app/schemas/mastery.py:12-22`) are covered by code review + manual probing, not automated eval.

## 4. Known blind spots

No claim-level entailment judge; no retrieval relevance labels (no NDCG/recall); no automated prompt-regression suite in CI; recommendation quality unevaluated (nothing persisted to judge). These are the first eval investments with more time.
