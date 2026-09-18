# AI Study Companion

An AI-powered learning workspace: upload PDFs, learn with a grounded AI tutor, take adaptive quizzes, track concept mastery, and watch growth over time — with an admin mission-control dashboard on top.

**Learning loop:** Space → Project → Upload material → Tutor (cited answers) → Quiz → Mastery → Growth → Recommendations → Continue.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 18 + Vite, Redux Toolkit, Framer Motion, Tailwind-style tokens |
| Backend | FastAPI (Python 3.11), Pydantic validation, JWT (jose) + bcrypt auth |
| AI | LangGraph tutor/quiz/assignment graphs; Inception Labs Mercury (OpenAI-compatible) for chat, Google Gemini embeddings (768-d) |
| Retrieval | pgvector (cosine search, strictly project-filtered) |
| Jobs | Celery + Redis (document ingest, quiz gen/grade, memory extraction) |
| DB | PostgreSQL 15 + pgvector (`Base.metadata.create_all` on boot; no Alembic) |

## Quickstart

```bash
# 1. Fill in keys (see Environment below) — .env is git-ignored, never commit it
cp .env.example .env   # if present, otherwise create .ev from the table below

# 2. Start everything
docker compose up -d --build

# 3. Open the app
# Frontend: http://localhost:5173   Backend health: http://localhost:8000/health
```

Default admin account (seeded on boot, override via `ADMIN_*`): `admin@gmail.com` / `12345`.

Seed demo evaluation data (optional):
```bash
docker compose exec backend python scripts/seed_evaluation.py   # --force to reseed
```

## Environment

| Variable | Required | What |
|---|---|---|
| `DATABASE_URL` | yes | Postgres URL (compose default works) |
| `SECRET_KEY` / `JWT_SECRET_KEY` | yes | JWT signing secret |
| `INCEPTION_API_KEY` | yes | Chat LLM — https://platform.inceptionlabs.ai/dashboard/api-keys |
| `INCEPTION_MODEL` | no | Default `mercury-2.5` |
| `GOOGLE_API_KEY` | yes | Gemini embeddings (retrieval needs this) |
| `REDIS_URL` | yes | Celery broker (compose default works) |
| `GROQ_API_KEY` / `GROQ_MODEL` | no | Disabled fallback — uncomment in code + `.env` to switch back |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_NAME` | no | Seeded admin account |
| `LANGCHAIN_*` | no | LangSmith tracing passthrough |

## Repo layout

```
backend/
  app/api/v1/        # REST routers: auth, spaces, projects, tutor, materials,
                     # quiz (+quiz_flat batch flow), mastery, assignment, analytics, admin
  app/ai/            # llm.py (provider switch), graphs/, nodes/, actions.py (quick actions),
                     # mastery_engine.py, concept_extractor.py, prompts.py
  app/tasks/         # Celery: documents, concepts, quiz, assignments, learning, analytics
  app/services/      # ai_usage metering, analytics/growth math, learning memory, assignments
  app/db/models/     # users, spaces, projects, documents+chunks, chat, assessment,
                     # mastery(+history), learning, ai_usage
  scripts/           # seed_evaluation.py, attribute_concept_sources.py
frontend/src/
  pages/             # Auth, Spaces, ProjectWorkspace (Materials, Concepts, AI Tutor,
                     # Quiz, Assignments, Analytics), GlobalAnalytics, Admin
  features/          # Redux slices: auth, project, tutor, quiz, assignments, concepts, analytics
  components/        # ui, Sidebar, Navbar, icons, ConfirmModal
  api/client.js      # axios client (LAN-aware base URL)
```

## Key flows

- **Tutor turn** (`POST …/conversations/{id}/tutor`): intent classify → RAG retrieve (top-5 chunks, this project only) → evidence grade → answer with `[Source: Page N]` citations → follow-ups. Quick actions (`summarize`, `deep_dive`, `create_flashcards`, `practice`) reuse the same pipeline with different directives; practice renders MCQs inline and never touches mastery. Greetings/small-talk never trigger generations.
- **Quiz**: batch generate (configurable MCQ + open mix) → save answers → submit → strict LLM grading with retries → mastery updates (70/30 blend) + history snapshots.
- **Mastery & growth**: `Concept.mastery_level` + append-only `MasteryHistory` (idempotent) → per-concept/project growth (improving/stable/attention) + rule-based recommendations.
- **Admin** (`/admin`, admin role): users + learning journey, spaces/projects, activity feed with filters, AI usage metering (calls/tokens/cost/latency per feature×provider×model×day), AI evaluation (tutor quality, retrieval grounding, assessment, recommendations), job states, system health.
- **Background work**: uploads, quiz gen/grade, concept extraction, conversation summaries, and memory extraction all run on Celery with retries; the UI polls status.

## Ports (docker-compose)

`5173` frontend · `8000` backend · `5433` postgres · `6379` redis.

## Known limitations (prototype)

- PDF text extraction only (PyMuPDF) — scanned/image pages yield no chunks; OCR path is stubbed out.
- No response streaming, no app-level caching, no pagination on some lists.
- Tutor turn has endpoint-level provider-error mapping but no per-node retry; no Alembic migrations.
- Quiz adaptivity is mastery-ordered batch generation (the one-question-at-a-time adaptive graph exists but isn't wired to UI).
- No voice, spaced repetition, notifications, or collaboration.
