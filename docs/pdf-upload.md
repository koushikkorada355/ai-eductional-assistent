# PDF Upload — What Happens & What To Do

Upload path: Materials tab → drag & drop / browse → `POST /api/v1/spaces/{spaceId}/projects/{projectId}/upload-pdf` (`backend/app/api/v1/materials.py`) → background job `documents.process` (`backend/app/tasks/document_tasks.py`) → parse (PyMuPDF + OCR fallback, `backend/app/utils/pdf_parser.py`) → split 1000/150 → Gemini embeddings → pgvector → concepts.

## Statuses (shown as badge in Materials list)

| Status | Meaning | What to do |
|---|---|---|
| `queued` | File saved, waiting for worker. Normal for a few seconds. | Wait ~30s, refresh list. If stuck >2 min, see Queue errors below, then press **Retry**. |
| `processing` | Worker is parsing/embedding now. | Wait. Do not re-upload. |
| `ready` | Searchable. Tutor + quiz can use it. `pages`/`chunks` counts filled in. | Open **View** → Extracted Evidence to confirm pages. |
| `failed` | Something stopped processing. The exact reason is shown **under the doc** (and in detail view). | Match the reason in the tables below, fix, press **Retry**. No re-upload needed (re-upload of same content gives 409). |

Where to look: Materials list shows `error` under failed/queued docs; open **View** for the same message + evidence excerpts (`GET .../documents/{id}/evidence`).

## Upload-time errors (red toast, no doc created)

| Message | Cause | Fix |
|---|---|---|
| `Only PDF files are allowed.` | Wrong type. | Choose a `.pdf` file. |
| `That file is empty.` / `Uploaded file is empty.` | 0-byte file. | Re-export the PDF. |
| `PDF too large (XMB). Max is 25MB.` (413) | Over `MAX_UPLOAD_MB` (default 25). | Compress/split the PDF or raise `MAX_UPLOAD_MB` on backend + redeploy. |
| `File is not a valid PDF (missing %PDF header).` | Renamed non-PDF. | Re-export as PDF. |
| `This file was already uploaded as '...'.` (409) | Same content hash in this project. | Use the existing doc. |
| `A file named '...' already exists in this project.` (409) | Same filename in this project. | Rename or delete old doc. |
| `Upload timed out.` | Slow network / huge PDF (>120s). | Smaller PDF or better connection, retry. |
| `Cannot reach server.` | Frontend can't reach backend at all. | Backend down/sleeping, wrong `VITE_API_BASE_URL` (baked at build), or offline. Open `<backend>/health` directly; check DevTools Network. |

## Processing errors (doc created, status `failed`, reason under doc)

Clients only ever see short coded messages (`[E_...]`, no URLs/paths/keys/API blobs) — the full reason stays in the server logs. Match the code below.

| Reason (shown under doc) | Cause | Fix |
|---|---|---|
| `[E_AI_AUTH] AI service refused the request...` | Embeddings key missing/invalid on worker, or provider rejected the call. | Check keys in server logs, set same `GOOGLE_API_KEY` on web + worker, redeploy, **Retry**. |
| `[E_STORAGE] Server storage had a problem...` | Web + worker don't share disk (upload file invisible to worker). | Mount same volume at `/data/uploads` in both services (single-container Render needs no setup), set `UPLOAD_DIR=/data/uploads` on both, redeploy, **Retry**. |
| `Uploaded file is empty (0 bytes)...` | Empty file reached worker. | Re-upload. |
| `PDF is password-protected...` | Encrypted PDF. | Remove password, re-upload. |
| `Cannot open PDF (corrupt or not a real PDF)...` | Corrupt file. | Re-export, re-upload. |
| `PDF has no pages.` | 0-page PDF. | Re-export, re-upload. |
| `No extractable text found...` | Image-only scan with no OCR result. | Provide readable scan / text-layer PDF, **Retry**. |
| `[E_AI_QUOTA] AI usage limit reached...` | Gemini free-tier quota exhausted (429). | Wait a minute, **Retry**. Persistent? Upgrade quota/billing. |
| `[E_TIMEOUT] The request timed out...` / `[E_CONN] Could not reach...` | Provider network/timeout. | **Retry** in a moment. |
| `PDF has N pages (max 300 per upload)...` / `produced N chunks (max 2000)...` | Doc too large for the worker (would OOM-crash it). | Split into smaller PDFs, upload each part. |
| Worker service itself shows `Crashed`/restarts on upload | Out-of-memory (large scan, 300→200 DPI OCR renders, giant embedding call) or 10-min task limit. | Push latest code (batched embeddings, OCR cap 50 pages, 200 DPI, 300-page/2000-chunk caps, child recycled at ~350MB), redeploy worker with `--concurrency=1`, re-upload smaller parts, **Retry**. If exit was `137`/`OOMKilled`, it was memory — smaller PDFs confirm. |
| `...background worker is unreachable (queue error: ...)` | Redis down / wrong `REDIS_URL` / worker offline. Upload tried async then inline; both failed. | See Queue errors. File is kept — **Retry** after fix. |

## Queue errors (stuck `queued`, or `worker is unreachable`)

1. Open `GET <backend>/health/queue` (public): tells `redis` vs `workers` apart.
2. `REDIS_URL is not set` → set same internal URL on web + worker, restart **web** (Celery caches it at import), Retry.
3. `does not resolve` + `redis://redis` → local hostname in prod. Copy Redis service **internal** URL into both, restart web, Retry.
4. `auth failed` → copy full URL with password into both, restart web, Retry.
5. `Redis ok but no workers` → **no consumer is listening** (this is the classic "works local, queued-only in prod"). Check in order:
   - **Render single-container (our setup):** Dashboard → service → **Dockerfile Path must be empty** (uses root `./Dockerfile` → `start-single.sh`) with **no custom Start/Docker Command override**. An override like `uvicorn ...` or building `backend/Dockerfile` starts web WITHOUT the Celery worker: uploads publish fine (Redis ok) but nobody consumes → `queued` forever. Fix: clear the override / Dockerfile path, redeploy.
   - Deploy logs must show **both** `[single] starting celery worker` **and** `[WORKER] ready ... tasks(N): documents.process, ...`. Only uvicorn lines = no worker in the container.
   - Split web+worker setup: worker must be Running (not stopped/scaled-to-0/crashed) on the SAME `REDIS_URL`.
   - Meanwhile **re-upload or Retry**: both verify a listening worker first and process **inline on web** when none reply, so docs degrade to slower inline instead of staying `queued`.
6. Uploads prefer async Celery but fall back to inline in web (`_dispatch_or_process_inline`), so a dead Redis/worker slows uploads (~10–30s) instead of stranding them — still fix Redis/worker for speed.

## Limits & notes

- PDF only, max 25MB default (`MAX_UPLOAD_MB`), no duplicate content or filenames per project.
- Retry is idempotent (clears old chunks, resets `error`); safe to press repeatedly.
- Delete removes doc + chunks + file.
- API responses never include the server file path (`DocumentOut` exposes `file_name` only).
- Render checklist (single container): root `./Dockerfile` (empty Dockerfile Path), no Start Command override, disk at `/data/uploads` + `UPLOAD_DIR=/data/uploads`, `REDIS_URL` wired from Key Value service, same `GOOGLE_API_KEY`/`DATABASE_URL`/`SECRET_KEY` as before; redeploy after env changes.
