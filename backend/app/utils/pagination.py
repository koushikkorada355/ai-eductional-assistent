"""Shared offset pagination for list endpoints.

Every paginated endpoint accepts:
  ?page=1            1-based page number
  ?page_size=20      rows per page (clamped to MAX_PAGE_SIZE)

and returns:
  {"items": [...], "total": N, "page": p, "page_size": s, "pages": P}

Two flavors:
- SQLAlchemy queries -> paginate_query() (COUNT + OFFSET/LIMIT in the DB)
- already-built Python lists (merged feeds, aggregates) -> paginate_list()
"""
from math import ceil
from typing import Any

from pydantic import BaseModel, Field

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class PageOut(BaseModel):
    items: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    pages: int = 0
    # Optional exact aggregates over the full filtered set (not just the
    # page), e.g. {"total":..,"completed":..}. Lets stat cards stay correct
    # at any scale without loading every row.
    summary: Any = None


def clamp_page(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, int(page or 1))
    page_size = min(max(1, int(page_size or DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
    return page, page_size


def paginate_query(query, page: int, page_size: int):
    """COUNT + OFFSET/LIMIT a SQLAlchemy query. Returns (items, total, page, page_size)."""
    page, page_size = clamp_page(page, page_size)
    total = query.order_by(None).count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total, page, page_size


def paginate_list(rows: list, page: int, page_size: int):
    """Slice an in-memory list. Returns (page_rows, total, page, page_size)."""
    page, page_size = clamp_page(page, page_size)
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start:start + page_size], total, page, page_size


def page_envelope(items: list, total: int, page: int, page_size: int) -> dict:
    pages = ceil(total / page_size) if total and page_size else 0
    return {"items": items, "total": total, "page": page,
            "page_size": page_size, "pages": pages}
