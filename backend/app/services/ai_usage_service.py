"""AI usage metering for the admin dashboard.

Two cooperating pieces:

1. TrackedLLM — wraps the object returned by get_llm(). Every invoke /
   ainvoke records {provider, model, prompt/completion tokens, latency,
   success} into the active operation bucket (contextvar). Token counts come
   from the provider's own response metadata (OpenAI-compatible token_usage
   / usage_metadata), so no LangSmith or extra API calls are needed. Cost is
   estimated from a per-model price table (USD per 1M tokens).

2. track_ai_call — decorator marking one billable AI operation (tutor turn,
   quiz generation, ...). On exit it writes ONE aggregated AIUsage row.
   Operations that use no LLM (cached / deterministic fast paths) write
   nothing on success, so "Calls" stays an accurate LLM-call count.

Everything here is failure-safe: metering must never break a tutor turn,
quiz, assignment, or background job.
"""
import contextvars
import functools
import inspect
import time
import uuid
from loguru import logger

from app.config import settings

try:
    from celery.exceptions import Retry as _CeleryRetry
except Exception:  # celery not installed (should not happen in backend)
    _CeleryRetry = None

# Active per-operation bucket; None outside a tracked operation.
_bucket: contextvars.ContextVar = contextvars.ContextVar("ai_usage_bucket", default=None)

# USD per 1M tokens (prompt, completion). Estimates for Groq-hosted models;
# unknown models fall back to _FALLBACK_PRICING and are still counted.
# NOTE: Inception/Mercury has no per-model entry (no verified price table
# at switch-over) so it uses _FALLBACK_PRICING — treat its costs as rough.
_MODEL_PRICING = [
    ("llama-3.3-70b-versatile", 0.59, 0.79),
    ("llama-3.1-70b-versatile", 0.59, 0.79),
    ("llama-3.1-8b-instant", 0.05, 0.08),
    ("kimi-k2-instruct", 1.00, 3.00),
    ("qwen3-32b", 0.29, 0.59),
    ("deepseek-r1-distill-llama-70b", 0.75, 0.99),
    ("gemma2-9b-it", 0.20, 0.20),
]
_FALLBACK_PRICING = (0.30, 0.60)


def estimate_cost(model: str | None, prompt_tokens: int, completion_tokens: int) -> float:
    name = (model or "").lower()
    for key, pin, pout in _MODEL_PRICING:
        if key in name:
            return round((prompt_tokens * pin + completion_tokens * pout) / 1_000_000, 6)
    pin, pout = _FALLBACK_PRICING
    return round((prompt_tokens * pin + completion_tokens * pout) / 1_000_000, 6)


def _default_provider() -> str:
    """Configured LLM provider when an operation used no metered call.

    Previously empty buckets were stored as provider='none', which the
    AI Usage table then showed as a missing provider name (e.g. for
    tutor turns that hit a deterministic fast path). Infer from config
    so the table always shows something meaningful.
    """
    try:
        if settings.INCEPTION_API_KEY:
            return "inception"
        if settings.GROQ_API_KEY:
            return "groq"
    except Exception:
        pass
    return "none"


def _default_model() -> str:
    try:
        return settings.INCEPTION_MODEL or settings.GROQ_MODEL or "unconfigured"
    except Exception:
        return "unconfigured"


def _resolve_provider(provider: str | None, model: str | None) -> str:
    """Backfill a truthful provider for rows stored with provider='none'.

    Old rows (and Fake-LLM dev rows) keep provider='none'. When the model
    is a real configured model, the provider was groq even though the
    bucket was empty — resolve it so the UI never shows a blank name.
    """
    p = (provider or "").strip().lower()
    m = (model or "").strip().lower()
    if p and p != "none":
        return p
    # Fake LLM without any key really did no provider call.
    if m in ("fake", "", "unconfigured"):
        return _default_provider()
    # Inception Labs (Mercury) models.
    if "mercury" in m or "inception" in m:
        return "inception"
    try:
        inception_model = (settings.INCEPTION_MODEL or "").strip().lower()
        if inception_model and (m == inception_model or inception_model in m or m in inception_model):
            return "inception"
    except Exception:
        pass
    try:
        groq_model = (settings.GROQ_MODEL or "").strip().lower()
        if groq_model and (m == groq_model or groq_model in m or m in groq_model):
            return "groq"
    except Exception:
        pass
    # Known groq-hosted family names fall back to groq.
    for key, _, _ in _MODEL_PRICING:
        if key in m:
            return "groq"
    if "groq" in m or "llama" in m or "qwen" in m or "kimi" in m or "gemma" in m or "deepseek" in m:
        return "groq"
    return _default_provider()


def _provider_model(inner) -> tuple[str, str]:
    cname = inner.__class__.__name__
    if "Fake" in cname:
        return "none", "fake"
    if "Groq" in cname:
        model = (getattr(inner, "model_name", None) or getattr(inner, "model", None)
                 or settings.GROQ_MODEL or "groq-unknown")
        return "groq", str(model)
    if "OpenAI" in cname:
        # ChatOpenAI is also used for Inception Labs (OpenAI-compatible API).
        base = str(getattr(inner, "openai_api_base", None)
                   or getattr(inner, "base_url", None) or "")
        model = (getattr(inner, "model_name", None) or getattr(inner, "model", None)
                 or settings.INCEPTION_MODEL or "openai-unknown")
        if "inception" in base.lower() or "mercury" in str(model).lower():
            return "inception", str(model)
        return "openai", str(model)
    return "other", cname


def _extract_tokens(res) -> tuple[int, int]:
    """(prompt_tokens, completion_tokens) from provider response metadata."""
    prompt, completion = 0, 0
    try:
        meta = getattr(res, "response_metadata", None) or {}
        tu = meta.get("token_usage") or {}
        prompt = int(tu.get("prompt_tokens") or 0)
        completion = int(tu.get("completion_tokens") or 0)
        if not (prompt or completion):
            um = getattr(res, "usage_metadata", None) or {}
            prompt = int(um.get("input_tokens") or 0)
            completion = int(um.get("output_tokens") or 0)
    except Exception:
        pass
    return prompt, completion


def _parse_uuid(value):
    if value is None:
        return None
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def log_ai_call(feature: str, success: bool = True, latency_ms: float | None = None,
                model: str | None = None, user_id=None, project_id=None,
                error: str | None = None, provider: str | None = None,
                prompt_tokens: int = 0, completion_tokens: int = 0,
                cost_usd: float = 0.0, calls: int = 1) -> None:
    """Insert one AIUsage row. Never raises."""
    try:
        from app.db.session import SessionLocal
        from app.db.models.ai_usage import AIUsage

        total = (prompt_tokens or 0) + (completion_tokens or 0)
        # Never persist a blank provider name: resolve 'none'/empty against
        # the model + configured keys (e.g. tutor fast-paths stored none).
        norm_provider = _resolve_provider(provider, model)
        norm_model = model or _default_model()
        db = SessionLocal()
        try:
            db.add(AIUsage(
                feature=feature,
                provider=norm_provider,
                model=norm_model,
                latency_ms=round(float(latency_ms), 1) if latency_ms is not None else None,
                success=bool(success),
                error=(error or "")[:1000] or None,
                user_id=_parse_uuid(user_id),
                project_id=_parse_uuid(project_id),
                prompt_tokens=int(prompt_tokens or 0),
                completion_tokens=int(completion_tokens or 0),
                total_tokens=int(total),
                cost_usd=float(cost_usd or 0.0),
                calls=int(calls or 1),
            ))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"[ai_usage] log skipped ({feature}): {e}")


def _record_event(provider, model, prompt_tokens, completion_tokens,
                  latency_ms, success, error=None) -> None:
    """Append one LLM-call event to the active bucket, or log it immediately
    as feature='other' when no operation is being tracked."""
    event = {"provider": provider, "model": model,
             "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
             "latency_ms": latency_ms, "success": success, "error": error}
    try:
        bucket = _bucket.get()
    except Exception:
        bucket = None
    if bucket is not None:
        try:
            bucket.append(event)
            return
        except Exception:
            pass
    try:
        log_ai_call(feature="other", success=success, latency_ms=latency_ms,
                    model=model, provider=provider, error=error,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=estimate_cost(model, prompt_tokens, completion_tokens),
                    calls=1)
    except Exception:
        pass


class TrackedLLM:
    """Transparent proxy around a LangChain chat model that meters tokens."""

    def __init__(self, inner):
        object.__setattr__(self, "_inner", inner)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(object.__getattribute__(self, "_inner"), name)

    def _meta(self):
        inner = object.__getattribute__(self, "_inner")
        return _provider_model(inner)

    def invoke(self, *args, **kwargs):
        inner = object.__getattribute__(self, "_inner")
        provider, model = self._meta()
        start = time.perf_counter()
        try:
            res = inner.invoke(*args, **kwargs)
        except Exception as e:
            _record_event(provider, model, 0, 0,
                          (time.perf_counter() - start) * 1000,
                          False, f"{type(e).__name__}: {e}")
            raise
        pt, ct = _extract_tokens(res)
        _record_event(provider, model, pt, ct,
                      (time.perf_counter() - start) * 1000, True)
        return res

    async def ainvoke(self, *args, **kwargs):
        inner = object.__getattribute__(self, "_inner")
        provider, model = self._meta()
        start = time.perf_counter()
        try:
            res = await inner.ainvoke(*args, **kwargs)
        except Exception as e:
            _record_event(provider, model, 0, 0,
                          (time.perf_counter() - start) * 1000,
                          False, f"{type(e).__name__}: {e}")
            raise
        pt, ct = _extract_tokens(res)
        _record_event(provider, model, pt, ct,
                      (time.perf_counter() - start) * 1000, True)
        return res


def _is_retry(exc: BaseException) -> bool:
    return _CeleryRetry is not None and isinstance(exc, _CeleryRetry)


def track_ai_call(feature: str, ctx_fn=None, ok_result=None):
    """Decorator logging one aggregated AIUsage row per operation.

    - Works on sync + async functions (Celery bind tasks included).
    - Celery `Retry` raises are still in-flight, so they are not logged.
    - Operations with zero LLM calls write nothing on success (keeps
      "Calls" an accurate LLM-call count) but still log failures.
    - `ctx_fn(*args, **kwargs)` may return {"user_id","project_id"}.
    - `ok_result(result)` decides success for string-status tasks
      (default: a "failed:..." string counts as failure).
    """
    def _ctx(args, kwargs):
        try:
            return (ctx_fn(*args, **kwargs) if ctx_fn else {}) or {}
        except Exception:
            return {}

    def _flush(bucket, start, success, error, ctx):
        try:
            wall_ms = (time.perf_counter() - start) * 1000
            pt = sum(e["prompt_tokens"] for e in bucket)
            ct = sum(e["completion_tokens"] for e in bucket)
            cost = sum(estimate_cost(e["model"], e["prompt_tokens"], e["completion_tokens"])
                       for e in bucket)
            if bucket:
                providers = [_resolve_provider(e["provider"], e["model"]) for e in bucket]
                models = [e["model"] for e in bucket]
                provider = max(set(providers), key=providers.count)
                model = max(set(models), key=models.count)
            else:
                # No metered LLM call (deterministic fast path). Resolve to the
                # configured provider so AI Usage never shows a blank name.
                provider, model = _default_provider(), _default_model()
            log_ai_call(feature=feature, success=success, latency_ms=wall_ms,
                        model=model, provider=provider,
                        user_id=ctx.get("user_id"), project_id=ctx.get("project_id"),
                        error=error, prompt_tokens=pt, completion_tokens=ct,
                        cost_usd=cost, calls=len(bucket))
        except Exception:
            pass

    def _ok(result):
        try:
            if ok_result is not None:
                return bool(ok_result(result))
            if isinstance(result, str) and result.startswith("failed:"):
                return False
            return True
        except Exception:
            return True

    def deco(fn):
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def a_wrapper(*args, **kwargs):
                bucket: list = []
                tok = _bucket.set(bucket)
                start = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                except Exception as e:
                    if not _is_retry(e):
                        _flush(bucket, start, False, f"{type(e).__name__}: {e}",
                               _ctx(args, kwargs))
                    raise
                finally:
                    _bucket.reset(tok)
                ok = _ok(result)
                if bucket or not ok:
                    _flush(bucket, start, ok,
                           None if ok else "operation reported failure",
                           _ctx(args, kwargs))
                return result
            return a_wrapper

        @functools.wraps(fn)
        def s_wrapper(*args, **kwargs):
            bucket: list = []
            tok = _bucket.set(bucket)
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
            except Exception as e:
                if not _is_retry(e):
                    _flush(bucket, start, False, f"{type(e).__name__}: {e}",
                           _ctx(args, kwargs))
                raise
            finally:
                _bucket.reset(tok)
            ok = _ok(result)
            if bucket or not ok:
                _flush(bucket, start, ok,
                       None if ok else "operation reported failure",
                       _ctx(args, kwargs))
            return result
        return s_wrapper
    return deco
