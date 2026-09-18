"""Client-safe error messages.

Rule: the SERVER logs the full raw failure (tracebacks, provider blobs,
paths) via loguru — the CLIENT only ever gets a short, stable, coded
message with no backend internals (no URLs, absolute paths, env var names,
API response bodies, exception class names, or tracebacks).

`public_error()` is applied at every boundary where text can reach a
client: Document.error (Materials list / evidence / retry responses),
HTTPException details, and graph error strings.
"""
from __future__ import annotations

import re

# Curated end-user messages the codebase already crafts (password, empty,
# no-pages, page/chunk caps, duplicates, bad header). They contain no leak
# patterns, so they pass through untouched (truncated to 500 chars).
# Anything else is mapped to a coded category below.

_LEAK_PATTERNS = (
    r"https?://",            # provider doc/billing URLs, links
    r"(^|[\s('\"=])(/[A-Za-z0-9_.\-]+)+",  # absolute server paths
    r"[A-Za-z]:\\",          # windows paths
    r"Traceback|File \"|\.py\"?,? line \d+|line \d+, in ",  # tracebacks
    r"API_KEY|SECRET_KEY|Bearer|token|password\s*=\s*\S+",   # secrets shape
    r"GOOGLE_|INCEPTION_|GROQ_|LANGCHAIN_|DATABASE_URL|REDIS_URL|UPLOAD_DIR",
    r"RESOURCE_EXHAUSTED|quota|billing|rate.?limit|429|401|403|500|503",
    r"celery|kombu|psycopg|sqlalchemy|uvicorn|onnx|CUDA|cuDNN",
    r"Exception|Error\s*:|Traceback|raise |assert ",
)


def _has_leak(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in _LEAK_PATTERNS)


def public_error(raw: str | Exception | None, *, default: str = "Processing failed") -> str:
    """Return a short client-safe message for `raw` (never raises)."""
    text = raw if isinstance(raw, str) else (str(raw) if raw is not None else "")
    text = (text or "").strip()
    if not text:
        return default
    low = text.lower()

    # Curated clean messages pass through (they match no leak pattern).
    if not _has_leak(text):
        return text[:500]

    # Leaking content: map to a stable coded message. The full `raw` must
    # already be in the server logs at the call site.
    if any(k in low for k in ("resource_exhausted", "quota", "rate limit", "rate_limit",
                              "429", "too many requests", "billing", "usage limit")):
        return ("[E_AI_QUOTA] AI usage limit reached. Wait a minute, then press Retry. "
                "(Owner: check provider quota/billing in server logs.)")
    if any(k in low for k in ("api key", "apikey", "api_key", "unauthorized", "unauthenticated",
                              "invalid key", "permissiondenied", "permission denied")) and \
            any(k in low for k in ("google", "gemini", "inception", "groq", "generativelanguage",
                                   "key", "auth", "credential")):
        return ("[E_AI_AUTH] AI service refused the request. "
                "(Owner: check API keys in server logs, then press Retry.)")
    if any(k in low for k in ("timed out", "timeout", "deadline exceeded", "timedout")):
        return "[E_TIMEOUT] The request timed out. Press Retry."
    if any(k in low for k in ("connection refused", "name or service not known", "nodename nor servname",
                              "temporary failure in name resolution", "network is unreachable",
                              "could not connect", "connection reset", "connection aborted")):
        return "[E_CONN] Could not reach a backend service. Try again in a moment."
    if any(k in low for k in ("password-protected", "password protected", "encrypted", "needs_pass",
                              "requires a password")):
        return "PDF is password-protected. Remove the password and re-upload."
    if any(k in low for k in ("no such file", "file not found", "not found on worker", "upload_dir",
                              "mount the same", "same volume", "volume", "disk", "no space", "enospc",
                              "permission denied", "read-only", "is a directory")):
        return ("[E_STORAGE] Server storage had a problem handling the file. "
                "(Owner: check UPLOAD_DIR/volume in server logs, then press Retry.)")
    if any(k in low for k in ("mupdf", "fitz", "pymupdf", "corrupt", "xref", "trailer", "catalog",
                              "startxref", "decrypt", "not a pdf", "%pdf", "cannot parse pdf",
                              "cannot open pdf")):
        return "This PDF could not be opened (corrupt or unsupported). Please re-export and upload again."
    return ("[E_UNKNOWN] Processing failed unexpectedly. The details were logged "
            "on the server — press Retry, and contact support with the time if it persists.")


def short_admin_detail(exc: Exception, *, limit: int = 160) -> str:
    """One-line admin-health detail: class + first line, no URLs/paths/blobs."""
    try:
        first = (str(exc) or "").strip().splitlines()[0]
    except Exception:
        first = ""
    first = re.sub(r"https?://\S+", "<url>", first)
    first = re.sub(r"(^|[\s('\"=])(/[A-Za-z0-9_.\-]+)+", r"\1<path>", first)
    detail = f"{type(exc).__name__}: {first}".strip()
    return detail[:limit] if detail else type(exc).__name__
