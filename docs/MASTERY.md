# How Mastery Is Updated

This document describes exactly how concept mastery changes in the AI Study
Companion backend. All paths are background Celery tasks or direct DB writes —
no endpoint recalculates mastery on read.

## The two mastery stores

| Store | Table / field | Written by | Read by |
|---|---|---|---|
| Project concept mastery | `concepts.mastery_level` (Float 0–100) + `last_assessed_at` | Quiz submit, tutor chat signal | Concepts tab, analytics, dashboard badges |
| Per-user mastery | `user_concept_mastery.mastery_score` (Int 0–100) | Legacy `POST /api/v1/quiz/submit` only | Legacy mastery endpoints (`/mastery/state`, `/recommendations`) |

The UI displays `concepts.mastery_level`. The per-user table is a separate
legacy track and is **not** updated by quizzes, assignments, or tutor chats
in the main application flow.

## Initial state

- Concept extraction (`tasks/concept_tasks.py` extract flow) creates one
  `Concept` row per concept with `mastery_level = 0.0` and
  `last_assessed_at = NULL`.
- Until something is assessed, every concept shows 0% ("Needs work").

## Update path 1 — quiz submission (main path)

Flow: `POST /quiz/{id}/submit` → `quiz.submit_task`
(`backend/app/tasks/quiz_tasks.py`) → per question
`mastery.update_from_quiz` (`update_mastery_from_quiz_task`, line ~90).

1. Each question is evaluated first:
   - **MCQ** (`_evaluate_mcq`): tolerant string match → score is exactly
     **100** (correct) or **0** (incorrect), plus a one-sentence LLM
     explanation as feedback.
   - **Open-ended** (`_evaluate_open`): LLM judge returns
     `{score 0–100, feedback, missing_concepts}` (3 retries; on total
     failure the question scores 0 with "Evaluation failed").
2. After all questions are evaluated, one mastery task runs per question:
   - Skipped (`skipped:no-concept-or-eval`) when the question has no linked
     concept or no evaluation.
   - Otherwise the concept's mastery is blended (line ~102):

     ```text
     new_mastery = round(old_mastery * 0.7 + question_score * 0.3, 2)
     ```

   - `last_assessed_at` is set to now.
3. The quiz is marked `completed` only after the mastery updates are queued.

### Worked example

Concept "Photosynthesis" at 50%. Quiz has 2 linked questions scoring
100 and 60:

```text
after Q1: 50 * 0.7 + 100 * 0.3 = 65.0
after Q2: 65 * 0.7 + 60 * 0.3  = 63.5
```

Each question moves mastery 30% of the way toward its own score, so recent
evidence matters most but history is never wiped out in one step.

## Update path 2 — tutor chat signal (silent path)

Flow: tutor `generate_answer` (`backend/app/ai/nodes/tutor_nodes.py`)
→ silent LLM judgement of the last 6 messages → if the user demonstrates
understanding, `mastery.update_from_chat`
(`update_mastery_from_chat_task` in `tasks/concept_tasks.py:86`) is
dispatched with `{concept_name, confidence_score}`.

- The concept name is normalized; invalid names are rejected
  (`skipped:invalid-name`).
- If the concept does not exist in the project, a semantic-duplicate check
  runs first; only a genuinely new concept is created (starting at 0.0).
- The update uses the **same 70/30 blend**:

  ```text
  new_mastery = round(old_mastery * 0.7 + confidence_score * 0.3, 2)
  ```

- `last_assessed_at` is set to now.
- This never *lowers* mastery punitively on its own — it fires only when
  understanding is detected. Reading tutor answers without demonstrating
  understanding changes nothing.

## Update path 3 — legacy adaptive quiz (separate track)

`POST /api/v1/quiz/submit` (`backend/app/api/v1/mastery.py:quiz_submit`)
writes the **per-user** track only:

- MCQ: exact (whitespace-tolerant) match → `+10` if correct, `−10` if wrong.
- Open-ended: LLM verdict → engine-defined `score_delta` (positive/negative).
- Result clamped to 0–100; stored in `user_concept_mastery` with
  `last_feedback`; every submit also appends a `QuizHistory` row
  (`is_correct`, feedback, timestamp).
- `Concept.mastery_level` is **not** touched by this endpoint
  (except that a missing `Concept` row is created at 0.0 so the
  per-user row has something to point at).

## What does NOT change mastery

- **Assignments** — grading writes `AssignmentSubmission.score/total/feedback`
  only; no mastery task exists for assignments (`assignment_tasks.py` has
  zero mastery references).
- **Uploads / document processing** — creates concepts at 0.0, never scores them.
- **Tutor answers by themselves** — only the detected-understanding signal
  updates anything.
- **Failed evaluations** — a question with no evaluation is skipped, never
  scored as 0 implicitly (except the open-ended total-failure fallback,
  which explicitly scores 0).

## Display thresholds (frontend only, no logic effect)

| Mastery | Badge |
|---|---|
| ≥ 70 | Strong (green) |
| 40–69 | Learning (indigo) |
| < 40 | Needs work (red) |

Quiz result rings use a separate 60% pass/fail cut-off for display.

## `overall_progress` note

`projects.overall_progress` defaults to `0.0` at creation
(`api/v1/projects.py:37`) and **nothing in the codebase recomputes it**
(no task or endpoint writes it besides manual PUT/PATCH). Project progress
bars, dashboard averages, and analytics space rollups therefore reflect
whatever was last set manually — concept mastery is the live signal, not
this column.

## Code pointers

- Quiz evaluation + mastery dispatch: `backend/app/tasks/quiz_tasks.py`
  (`submit_quiz` flow ~line 220–262, `update_mastery_from_quiz_task` ~90–112,
  `_evaluate_mcq` ~128, `_evaluate_open` ~148)
- Chat signal + update: `backend/app/ai/nodes/tutor_nodes.py`
  (`generate_answer` ~130–185), `backend/app/tasks/concept_tasks.py:86–121`
- Legacy per-user track: `backend/app/api/v1/mastery.py`
  (`quiz_submit` ~135, history ~245)
- Tables: `backend/app/db/models/assessment.py` (`Concept`),
  `backend/app/db/models/mastery.py` (`UserConceptMastery`, `QuizHistory`)

---

# Learning Growth (built on top of the above)

Growth = change in `Concepts.mastery_level` over time, in percentage
points (pts). Mastery math is untouched; growth only reads history.

## History storage

- Table `mastery_history` (`app/db/models/mastery.py`): `user_id`,
  `project_id`, `concept_id`, `mastery`, `source` (`quiz`|`chat`|`baseline`),
  `source_id` (quiz-question id for quiz rows), `created_at`.
- Written by the same two tasks that update mastery
  (`update_mastery_from_quiz_task`, `update_mastery_from_chat_task`), in a
  **separate transaction after** the mastery commit — a history failure can
  never corrupt a mastery update.
- First snapshot for a concept also inserts a `baseline` row with the
  pre-update value (timestamped at concept creation), so growth has an
  honest starting point. Pre-existing concepts get their baseline lazily on
  the next real update — no backfill migration needed.
- Idempotency: unique `(concept_id, source, source_id)` — reprocessing the
  same quiz question returns `duplicate:already-recorded` instead of a
  second row (verified live against Postgres).
- Ownership: every row carries `user_id` + `project_id`; both analytics
  endpoints scope by project (`get_owned_project`) or by the caller's own
  projects, so no cross-user/project leakage.

## Calculation (`app/services/analytics_service.py`)

- Per concept: `growth = current − earliest measurement`; `recent` uses the
  last 4 observations; trend thresholds `>+5 improving`, `±5 stable`,
  `<−5 attention` (`TREND_THRESHOLD_PTS`, `RECENT_WINDOW`).
- Single measurement → `growth: null`, trend `insufficient` (UI shows "—"
  / "Not enough data"). Empty history → same.
- Project overall: average of initials vs average of currents, over concepts
  **with** history only.
- Chart series: carry-forward average across concepts at each event date
  (no interpolation invented), capped at 60 points.
- Insights are templated from the numbers only — no invented causes.

## API (all additive)

- Project analytics gains `growth: {overall, concepts[], series[]}` plus
  growth-driven recommendations (declining → review, improving-but-weak →
  keep practicing, strong+stable → focus elsewhere).
- Overview gains `growthByProject: {projectId: {initial, current, growth,
  trend}}` (single history query).
- Frontend: Analytics tab has Learning Growth card, SVG mastery-over-time
  chart with 7/30/90/All ranges (overall baseline never moves with the
  range), and per-concept growth cards; global page chips show `+x pts`.
- Tests: `backend/tests/test_growth.py` — 10/10 passing (increase,
  decrease, stable, single-point, empty, independence, isolation, series,
  thresholds).
