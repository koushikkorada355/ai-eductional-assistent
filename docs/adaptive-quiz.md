# Adaptive Quiz — Full Technical Reference

The Adaptive Quiz is a structured assessment loop, not rapid-fire chat. A quiz is
generated **upfront** from the project's own documents, the user answers at their
own pace with **save-and-submit**, and only the final submit triggers AI grading
plus mastery updates.

Code map: AI graphs live in `backend/app/ai/` (`state/` = state shapes,
`nodes/` = node functions, `graphs/` = wiring). API in
`backend/app/api/v1/quiz_flat.py`. Background work in
`backend/app/tasks/quiz_tasks.py` + `concept_tasks.py`. UI in
`frontend/src/pages/ProjectWorkspace/Tabs/Quiz/` + `features/quiz/`.

---

## 1. Data Model (`backend/app/db/models/assessment.py`)

| Table | Purpose | Key fields |
|---|---|---|
| `concepts` | Skills extracted from docs, per project | `name`, `mastery_level` (0–100), `last_assessed_at` |
| `quizzes` | One assessment attempt | `name`, `goal`, `status` (`generating` → `in_progress` → `evaluating` → `completed`/`failed`) |
| `quiz_questions` | One question | `question_type` (`multiple_choice`/`open_ended`), `question_text`, `options`, `correct_answer`, `user_answer`, `evaluation` JSON |

Pydantic validators (`backend/app/schemas/quiz.py`): `ConceptList`,
`ChatMasterySignal`, `OpenEndedEvaluation{score, feedback, missing_concepts}`,
`MCQQuestion{question_text, options[4], correct_answer}` — every LLM JSON output
is parsed through one of these (3 retries) before it touches the database.

---

## 2. Quiz LangGraph — every node (`nodes/quiz_nodes.py`, wired in `graphs/quiz_graph.py`)

State (`state/quiz_state.py :: QuizState`): `project_id`, `quiz_id`, `messages`,
`current_question`, `current_question_id`, `question_type`, `user_answer`,
`evaluation`, `concepts_to_test`, `selected_concept`, `selected_concept_id`,
`questions_asked`, `error`. Checkpointer: `AsyncPostgresSaver` with
`thread_id = quiz_id`, so a quiz survives server restarts.

### assess_mastery
Queries `concepts` for this `project_id` only (strict isolation), ordered by
lowest `mastery_level` then oldest `last_assessed_at`. Picks the weakest concept
into `selected_concept`/`selected_concept_id` plus the top-5 names into
`concepts_to_test`. If the project has no concepts (no PDFs processed yet), sets
`error = "No concepts found. Upload PDFs first."`.

### quiz_error
Terminal node for the no-concepts case. Emits the error as a chat message and the
graph ends. The start endpoint translates this into `status = failed`.

### generate_question
The interrupt point of the legacy one-by-one loop: builds one grounded question,
persists it with `user_answer = null`, bumps `questions_asked`, appends the
question text to `messages`, and the graph ends — the question is returned to
the caller instead of continuing.

### evaluate_answer
Writes `user_answer` to the row, then branches on type:
- **MCQ** — tolerant match (exact case-insensitive, letter-only like `"A"` vs
  `"A. Chlorophyll a"`, or prefix match). Score 100/0, plus a 1-sentence LLM
  explanation of the correct answer. Saved synchronously.
- **Open-ended** — dispatches Celery `quiz.evaluate` and returns a
  `pending: true` placeholder so the API responds instantly.

### update_mastery
Runs the shared mastery math for MCQs (open-ended waits for its Celery chain),
then stamps `last_assessed_at` on the concept.

### Route functions
- `route_after_assess` — `error` set → `quiz_error`, else `generate_question`.
- `route_loop` — `questions_asked >= MAX_QUESTIONS (5)` → `END`, else back to
  `assess_mastery` (the cycle).

### Graph wiring
`START → assess_mastery → {generate_question → END | quiz_error → END}`,
plus `evaluate_answer → update_mastery → {assess_mastery | END}`.

### Batch helpers (used by the current save-and-submit flow, same file)
- `_rag_context(db, project_id, query)` — top-5 `pgvector` chunks strictly
  filtered by `project_id`; empty string on failure, never raises.
- `_craft_question(concept, context, qtype)` — LLM generation with 3 retries
  and a deterministic fallback question.
- `select_concepts_for_goal(project_id, goal, n)` — weakest-first concepts
  re-ranked by an LLM for relevance to the quiz goal (falls back to
  weakest-first).
- `generate_quiz_batch(project_id, quiz_id, goal, num_mcq, num_open)` — custom split,
  alternating MCQ/open-ended, persists N distinct rows, returns their ids.
- `concept_name_for_eval(question, state)` — resolves the concept name from the
  DB when the state doesn't carry it, so `missing_concepts` is never blank.

---

## 3. Tutor LangGraph — every node (`nodes/tutor_nodes.py`, `graphs/tutor_graph.py`)

State (`state/tutor_state.py :: TutorState`): `user_question`, `project_id`,
`messages`, `retrieved_context`, `sufficient_evidence`, `final_answer`, `intent`.

### detect_intent (runs first)
Fast LLM call classifying the message as `general` (greeting, small talk,
"what can you do", thanks, goodbye) or `knowledge` (asks about material).
Any classifier failure defaults to `knowledge` so real questions are never lost.

### Route: route_intent
`general` → `general_chat`; anything else → `retrieve_context`.

### general_chat (Path A)
Answers conversationally as the Study Companion — what it can do, friendly
small talk — completely bypassing retrieval, then ends.

### retrieve_context (Path B start)
Embeds the question with `gemini-embedding-001` (768 dims) and fetches the top-5
chunks filtered by `project_id`.

### grade_documents
LLM judges whether the retrieved chunks actually answer the question; outputs
strictly `yes`/`no` into `sufficient_evidence`.

### Route: route_evidence
Sufficient → `generate_answer`, else `reject_answer`.

### generate_answer
Strict grounded answer: uses ONLY the context, cites every factual claim as
`[Source: Page X]`. Before answering it also runs a **silent mastery probe** —
an LLM check whether the user demonstrates concept understanding, validated via
`ChatMasterySignal`, which dispatches `mastery.update_from_chat` (70/30 moving
average). Mastery therefore grows through conversation, not just quizzes.

### reject_answer
Terminal refusal: `"I cannot answer this based on the provided materials."` —
never hallucinates.

### Graph wiring
`START → detect_intent → {general_chat → END | retrieve_context →
grade_documents → {generate_answer → END | reject_answer → END}}`.

---

## 4. Celery Tasks

| Task (`tasks/`) | Trigger | Job |
|---|---|---|
| `documents.process` | PDF upload | Parse → chunk (1000/150) → Gemini embed → `ready`; chains concept extraction |
| `concepts.extract` | After document ready | LLM top-5 concepts → Pydantic validate → idempotent insert (`mastery 0.0`), 3 retries |
| `mastery.update_from_chat` | Tutor silent probe | `new = old*0.7 + confidence*0.3` |
| `quiz.generate_batch` | Quiz creation | Section-2 batch flow → status `in_progress` (or `failed`), 2 retries |
| `quiz.evaluate` | Legacy open-ended answer | Grade one answer, chain mastery task, 3 retries |
| `quiz.evaluate_submission` | Quiz submit | Grade **all** saved answers (MCQ sync, open-ended via LLM), update every concept, mark `completed`, 2 retries |
| `mastery.update_from_quiz` | After any grading | Same 70/30 formula + `last_assessed_at` stamp |

---

## 5. API Flow (`api/v1/quiz_flat.py`, ownership via `get_owned_project_by_id` / `get_owned_quiz`)

```
POST /projects/{id}/quiz/start  {name, goal?, num_mcq, num_open}
  → row (generating) + batch task → poll ──► in_progress + N questions
PATCH /quiz/{id}/questions/{qid}/save  {answer}
  → stores answer only. No grading, nothing revealed. 400 once completed.
POST /quiz/{id}/submit
  → evaluating + submission task ──poll──► completed
GET /quiz/{id}
  → questions + answers; correct_answer/evaluation present ONLY when completed
GET /projects/{id}/quizzes
  → attempts with average scores
```

Legacy one-by-one endpoints (`quizzes/start`, per-answer grading) remain on the
nested routes for backward compatibility; the UI uses the flow above.

---

## 6. Frontend (`Quiz.jsx` + `features/quiz/`)

- **Setup view** — name + goal form → creates the quiz; previous attempts listed
  (completed ones openable for review).
- **Generating / Evaluating views** — spinners driven by 4-second status polling.
- **Active view** — current question (MCQ cards or textarea), **Save** persists
  the draft, **Previous/Next** navigate freely, tracker shows
  saved / active / unattempted. Concepts and scores are never displayed here.
- **Results view** — score ring, per-question submitted vs correct answers, AI
  feedback and missing concepts, then mastery bars elsewhere reflect the update.

---

## 7. Guarantees

- **Ownership** — project → space → owner (or quiz → project → space → owner)
  on every call; foreigners get 403, unknowns 404.
- **No leakage** — correct answers and evaluations are stripped from reads until
  completion; submitted quizzes reject further saves; per-answer submits on a
  completed quiz return 400.
- **Idempotency** — duplicate question text reused, re-submits short-circuit,
  concept names unique per project.
- **Observability** — Loguru at every node entry/exit and inside each task with
  `project_id` / `quiz_id` / concept name; LangSmith traces LLM calls.
