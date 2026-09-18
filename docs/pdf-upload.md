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

| Reason (truncated) | Cause | Fix |
|---|---|---|
| `GOOGLE_API_KEY is not set on the worker...` | Embeddings key missing on worker. | Set same `GOOGLE_API_KEY` on web + worker, redeploy, **Retry**. |
| `Upload file not found on worker (path=...)... mount the SAME Railway volume... UPLOAD_DIR=/data/uploads` | Web + worker don't share disk. | Mount same volume at `/data/uploads` in both services, set `UPLOAD_DIR=/data/uploads` on both, redeploy, **Retry**. |
| `Uploaded file is empty (0 bytes)...` | Empty file reached worker. | Re-upload. |
| `PDF is password-protected...` | Encrypted PDF. | Remove password, re-upload. |
| `Cannot open PDF (corrupt or not a real PDF)...` | Corrupt file. | Re-export, re-upload. |
| `PDF has no pages.` | 0-page PDF. | Re-export, re-upload. |
| `No extractable text found...` | Image-only scan with no OCR result. | Provide readable scan / text-layer PDF, **Retry**. |
| `Embedding failed (check GOOGLE_API_KEY/quota)...` | Gemini key invalid / quota / network. | Fix key/quota, **Retry**. |
| `...background worker is unreachable (queue error: ...)` | Redis down / wrong `REDIS_URL` / worker offline. Upload tried async then inline; both failed. | See Queue errors. File is kept — **Retry** after fix. |

## Queue errors (stuck `queued`, or `worker is unreachable`)

1. Open `GET <backend>/health/queue` (public): tells `redis` vs `workers` apart.
2. `REDIS_URL is not set` → set same internal URL on web + worker, restart **web** (Celery caches it at import), Retry.
3. `does not resolve` + `redis://redis` → local hostname in prod. Copy Redis service **internal** URL into both, restart web, Retry.
4. `auth failed` → copy full URL with password into both, restart web, Retry.
5. `Redis ok but no workers` → worker service not Running or on different `REDIS_URL`. Fix + restart worker, Retry.
6. Uploads prefer async Celery but fall back to inline in web (`_dispatch_or_process_inline`), so a dead Redis slows uploads (~10–30s) instead of stranding them — still fix Redis for speed.

## Limits & notes

- PDF only, max 25MB default (`MAX_UPLOAD_MB`), no duplicate content or filenames per project.
- Retry is idempotent (clears old chunks, resets `error`); safe to press repeatedly.
- Delete removes doc + chunks + file.
- Railway checklist: same `REDIS_URL`, `GOOGLE_API_KEY`, `DATABASE_URL`, `SECRET_KEY` on web + worker; same `/data/uploads` volume + `UPLOAD_DIR`; redeploy both to same commit after env changes.
