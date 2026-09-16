"""Shared LLM concept-extraction utility.

Single source of truth for turning learning text into clean concept records.
Imported by the document ingestion pipeline (and available to the AI Tutor
chat flow). LangSmith tracing is automatic via LANGCHAIN_TRACING_V2 /
LANGCHAIN_API_KEY / LANGCHAIN_PROJECT env vars.
"""
import json
import re
from loguru import logger
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from app.ai.llm import get_llm

CONCEPT_EXTRACTION_PROMPT = """You are an educational content analyzer. Read the following learning material and extract the core academic concepts.

STRICT RULES:
1. Concepts MUST be short topic names, noun phrases, or section headers (e.g., 'Mitochondria', 'Linear Equations', 'Supply and Demand').
2. DO NOT extract full sentences or questions as concepts.
3. DO NOT extract generic words like 'Introduction', 'Summary', 'Overview', or 'Chapter 1'.
4. Extract ONLY the most important distinct concepts (at most 7), ranked by importance for learning. Skip minor details, examples, and passing mentions.

Material Text:
{text}

Output a JSON object with a single key 'concepts' containing an array of objects. Each object must have:
- `name`: (String) The short concept name (maximum 5 words).
- `description`: (String) A brief 1-2 sentence explanation of the concept based on the text."""

# Generic boilerplate that is never a real concept (matched case-insensitively;
# numbered variants like "Chapter 1" / "Unit 3" handled by _NUMBERED_RE).
GENERIC_TERMS = {
    "introduction", "conclusion", "overview", "summary", "contents",
    "preface", "foreword", "epilogue", "prologue", "appendix", "glossary",
    "index", "references", "bibliography", "acknowledgements",
    "acknowledgment", "abstract", "table of contents",
}
_NUMBERED_RE = re.compile(r"^(chapter|unit|lesson|part|section|module|exercise|question)\s*\d+", re.IGNORECASE)


class ConceptItem(BaseModel):
    name: str
    description: str = ""


class ConceptExtraction(BaseModel):
    concepts: list[ConceptItem] = Field(default_factory=list)


def _is_generic(name: str) -> bool:
    lowered = name.strip().lower()
    return lowered in GENERIC_TERMS or bool(_NUMBERED_RE.match(lowered))


def _is_valid_name(name: str) -> bool:
    clean = (name or "").strip()
    if not clean or clean.endswith("?"):
        return False
    if len(clean.split()) > 5:
        return False
    return True


def normalize_for_match(name: str) -> str:
    """Lowercased alphanumeric fingerprint for duplicate detection."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def find_semantic_duplicate(db, project_id, name: str, threshold: float = 0.86):
    """Return the existing Concept in this project that semantically matches
    `name`, or None. Exact normalized match first, then embedding similarity."""
    from app.db.models.assessment import Concept

    existing = db.query(Concept).filter(Concept.project_id == project_id).all()
    fingerprint = normalize_for_match(name)
    for c in existing:
        if normalize_for_match(c.name) == fingerprint:
            return c
    if not existing:
        return None
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        from app.config import settings

        emb = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-001",
            google_api_key=settings.GOOGLE_API_KEY,
            output_dimensionality=768,
        )
        vectors = emb.embed_documents([name] + [c.name for c in existing])
        import math

        def cosine(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            return dot / (na * nb) if na and nb else 0.0

        best, best_score = None, 0.0
        for concept, vec in zip(existing, vectors[1:]):
            score = cosine(vectors[0], vec)
            if score > best_score:
                best, best_score = concept, score
        if best is not None and best_score >= threshold:
            logger.info(f"[concept_extractor] semantic duplicate {name!r} ~ {best.name!r} ({best_score:.2f})")
            return best
    except Exception as e:
        logger.warning(f"[concept_extractor] similarity check failed: {e}")
    return None


def extract_concepts(text: str) -> list[dict]:
    """Extract clean concepts from learning text.

    Returns a list of {"name", "description"} dicts. Names longer than
    5 words, sentences/questions, and generic boilerplate are dropped.
    """
    if not (text or "").strip():
        return []
    llm = get_llm()
    last_err = None
    for attempt in range(3):
        try:
            res = llm.invoke(
                [
                    SystemMessage(content="You extract academic concepts as strict JSON. No other text."),
                    HumanMessage(content=CONCEPT_EXTRACTION_PROMPT.format(text=text[:12000])),
                ]
            )
            raw = res.content.strip().replace("```json", "").replace("```", "").strip()
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                parsed = {"concepts": parsed}
            items = ConceptExtraction(**parsed).concepts
            if not items:
                raise ValueError("no concepts returned, retry")
            if all(not (i.description or "").strip() for i in items):
                raise ValueError("missing descriptions, retry")
            break
        except Exception as e:
            last_err = e
            logger.warning(f"[concept_extractor] parse retry {attempt + 1}/3: {e}")
    else:
        raise last_err or RuntimeError("concept extraction failed")

    clean_items: list[dict] = []
    seen: set[str] = set()
    for item in items:
        name = (item.name or "").strip().strip('"')
        if not _is_valid_name(name):
            logger.debug(f"[concept_extractor] dropping invalid name {name!r}")
            continue
        if _is_generic(name):
            logger.debug(f"[concept_extractor] dropping generic term {name!r}")
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        clean_items.append({"name": name[:200], "description": (item.description or "").strip()[:1000]})
    logger.info(f"[concept_extractor] {len(items)} raw -> {len(clean_items)} clean")
    return clean_items
