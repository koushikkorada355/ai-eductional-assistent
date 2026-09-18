# AI Usage — AI Study Companion

> How AI is used in this project: the coding assistant that built it, the
> LLM and embedding models that power it, and which feature uses what.
> (Prompts log: `prompt.md`.)

## 1. Coding assistant

This project was built with **OpenCode**, powered by **Muse Spark** (Meta's
large language model). OpenCode acted as the coding agent: reading the
codebase, implementing backend endpoints and Celery tasks, building the React
frontend, debugging errors via Docker logs, and verifying fixes end to end.
Every user prompt that drove the build is logged in `prompt.md`.

## 2. Chat LLM — Inception Mercury (primary), Groq (standby)

All conversational and generative AI goes through `app/ai/llm.py:get_llm()`:

- **Priority 1 (active): Inception Labs Mercury**, default model
  `mercury-2.5`, called through its OpenAI-compatible API
  (`INCEPTION_BASE_URL`, default `https://api.inceptionlabs.ai/v1`) with
  `INCEPTION_API_KEY`. Temperature 0.7 for generation; the tutor's grounded
  nodes use 0.2 for factual answers.
- **Priority 2 (standby): Groq** (`ChatGroq`, `GROQ_MODEL`) — kept as a
  working fallback, activated by setting `GROQ_API_KEY`.
- **No key:** a fake model replies "AI tutor is temporarily unavailable",
  so the app never crashes without keys.

Every LLM call is wrapped in `TrackedLLM`
(`app/services/ai_usage_service.py`), which meters tokens and latency per
call into the `AIUsage` table. The admin dashboard's AI Usage view aggregates
calls/tokens/latency per user, per project, and per model, and the AI
Evaluation view aggregates quiz/assignment scores, pass rates, and trends —
so model cost and model quality are both visible in one place.

### Model configuration reference

| Purpose | Variable | Default / value |
|---|---|---|
| Chat LLM key | `INCEPTION_API_KEY` | (secret, required for tutor/quiz) |
| Chat model | `INCEPTION_MODEL` | `mercury-2.5` |
| Chat base URL | `INCEPTION_BASE_URL` | `https://api.inceptionlabs.ai/v1` |
| Fallback key | `GROQ_API_KEY` | (standby) |
| Fallback model | `GROQ_MODEL` | (standby) |
| Embeddings key | `GOOGLE_API_KEY` | (required for RAG) |
| Embedding model | (fixed in code) | `gemini-embedding-001`, 768-dim |
| Tracing | `LANGCHAIN_TRACING_V2` / `LANGCHAIN_API_KEY` / `LANGCHAIN_PROJECT` | `ai-study-companion` |
| OCR key | `OCR_API_KEY` | (tesseract fallback otherwise) |
| Visual RAG | `COLIVARA_API_KEY` | (commented standby) |

The fallback chain is strict: Inception if its key is set, else Groq if its
key is set, else a fake model that replies "AI tutor is temporarily
unavailable" — the app never crashes on missing keys, and every branch is
reported on the admin System Health view.

## 3. Embedding model — Google Gemini (768-dim)

Retrieval uses **Google Gemini `gemini-embedding-001`** via
`GoogleGenerativeAIEmbeddings` (`GOOGLE_API_KEY`), outputting **768
dimensions** stored in a pgvector `Vector(768)` column on `DocumentChunk`.
The same model embeds both document chunks (batched, ~32 per call) and user
questions, so query and chunk vectors are comparable. It is used in three
places: tutor context retrieval (`tutor_nodes.py`), quiz grounding
(`quiz_nodes.py`), and concept extraction (`concept_extractor.py`).
Without `GOOGLE_API_KEY`, ingestion fails with a coded client message while
the raw provider error stays in server logs.

## 4. Feature-by-feature model map

| Feature | Model | Use |
|---|---|---|
| AI Tutor RAG answer | Mercury (`mercury-2.5`) | Grounded answer + `[Source: Page X]` citations |
| Intent router | Mercury | General-chat vs RAG branching |
| grade_documents | Mercury | Yes/no chunk relevance grading |
| Follow-up suggestions | Mercury | Questions grounded in concepts + conversation only |
| Concept extraction | Mercury + Gemini embeddings | Key concepts per project, mastery bootstrap |
| Silent mastery eval | Mercury | Chat-based understanding scoring |
| Quiz generation (MCQ/open) | Mercury | Questions + rubrics grounded in chunks |
| Quiz evaluation | Mercury (open-ended) / exact match (MCQ) | Rubric scoring + feedback |
| Assignment generation/eval | Mercury | MCQ sets from weak concepts, deterministic grading |
| Chunk/query vectors | Gemini `gemini-embedding-001` | Retrieval for tutor, quiz, concepts |

## 5. Observability, OCR, and spares

- **LangSmith** (`LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`,
  `LANGCHAIN_PROJECT=ai-study-companion`) traces LLM calls for debugging
  prompt and pipeline behavior.
- **OCR**: `OCR_API_KEY` service first, tesseract binary fallback inside the
  container for scanned/image-only PDFs before declaring "no extractable
  text".
- **ColiVara** visual-RAG (`COLIVARA_API_KEY`) is kept as commented standby
  code, not active.

## 6. Prompting practices

System prompts enforce: answer only from retrieved context, cite pages,
suggest only answerable follow-ups, never emit backend details to clients.
Generation temperature stays low (0.2) for factual paths and 0.7 for creative
ones (suggestions, question writing). Retrieval is capped (top-5 chunks,
history window of last N turns) to bound tokens, latency, and cost per call.

Concretely, each LangGraph node carries its own narrow prompt: the intent
router classifies general vs materials questions; the grader answers only
yes/no on chunk relevance; the generator must attach `[Source: Page X]` to
factual claims; the suggester may only propose questions answerable from the
current concepts and conversation; quiz generation must stay inside the
supplied chunks; open-ended evaluation must follow the generated rubric and
award zero (never 100) for blank answers. When evidence is insufficient, the
reject path guides the user (upload more, rephrase) instead of dead-ending.

## 7. Cost, latency, and failure behavior

Expensive calls are bounded by design: embeddings run in small batches;
retrieval is top-5 with a similarity floor; chat history is windowed; answers
and suggestions have length limits. Slow or failed provider calls surface as
short coded client messages (`[E_AI_QUOTA]` ask to wait-and-retry,
`[E_TIMEOUT]`/`[E_CONN]` ask to retry in a moment, `[E_AI_AUTH]` points the
owner at keys) while the full provider response stays in server logs. Quota
exhaustion therefore degrades to "wait a minute, press Retry" instead of an
error dump, and a missing key degrades to the fake-model notice instead of a
500.
