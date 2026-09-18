# AI Usage — Build-Time AI vs Product AI

Per spec §20.5 (Final Submission Requirements, item 5). No credentials are recorded here; runtime keys live only in `.env` (see `.env.example`).

## 1. AI used to BUILD the product

- **AI coding assistants / development agents** — scaffolding, feature implementation, debugging, refactors, and UI overhauls across `backend/` and `frontend/`. The raw log of development prompts is `prompt.md` (dated entries, 2026-09-15 onward), which doubles as the §20.6 development-prompts record.
- **Design assistance** — frontend redesign iterations (LMS dashboard look, admin operations-center UI, auth screens); final styles committed as code under `frontend/src/`.
- **What AI did not do** — architecture choices, provider selection, the 70/30 mastery formula, growth math, and security boundaries were human decisions; AI output was reviewed against the repo (evidence: hardened follow-ups to blank-grading, suggestion-quality, and concept-name validation fixes recorded in `prompt.md`).

## 2. AI used BY the final product

| Capability | Provider / model | Code |
|------------|------------------|------|
| Tutor answers, intent classification, evidence grading, follow-up suggestions, history compression, chat mastery signal | Inception Labs Mercury (`INCEPTION_MODEL`, default `mercury-2.5`), OpenAI-compatible API; Groq kept as commented fallback; deterministic Fake fallback when unconfigured | `backend/app/ai/llm.py:12-30`, `backend/app/ai/nodes/tutor_nodes.py` |
| Concept extraction (≤7 topics, strict JSON) | Same chat LLM | `backend/app/ai/concept_extractor.py:15-29,112-162` |
| Quiz question generation, open-ended grading, MCQ explanations, adaptive concept selection, legacy recommendations | Same chat LLM, 3-attempt strict-JSON parsing into Pydantic models | `backend/app/ai/nodes/quiz_nodes.py:81-117`, `backend/app/tasks/quiz_tasks.py:213-237`, `backend/app/ai/mastery_engine.py` |
| Embeddings for ingest, tutor retrieval, quiz grounding, semantic concept dedupe | Google Gemini `gemini-embedding-001`, 768 dimensions, stored in pgvector `Vector(768)` | `backend/app/tasks/document_tasks.py:35`, `backend/app/ai/nodes/tutor_nodes.py:352-356`, `backend/app/db/models/document.py:27` |
| Scanned-page OCR fallback | Tesseract OCR binary (non-LLM) | `backend/app/utils/pdf_parser.py:17-33`, `backend/Dockerfile` |
| Tracing (optional) | LangSmith via `LANGCHAIN_*` env passthrough | `backend/app/ai/mastery_engine.py:1-5` |

Every LLM JSON output is validated through Pydantic (`SelectorDecision`, `GeneratedQuestion`, `EvaluatorVerdict`, `MCQQuestion`, `ConceptExtraction`, `OpenEndedEvaluation`, `ChatMasterySignal`) with retries before anything is persisted. Every LLM call is metered (provider, model, tokens, latency, estimated cost) into `ai_usage` and visible at `GET /admin/ai-usage` (`backend/app/services/ai_usage_service.py`).

## 3. Cost / failure posture

- Token counts come from provider response metadata; Mercury costs use a fallback price table and are rough estimates (`ai_usage_service.py:39-60`).
- Provider errors map to HTTP 429/502, never raw 500s (`app/api/v1/tutor.py:29-54`); quiz/grading/concept tasks retry 2–3×; blank open-ended answers score 0 without an LLM call (`app/tasks/quiz_tasks.py:27-47`).
