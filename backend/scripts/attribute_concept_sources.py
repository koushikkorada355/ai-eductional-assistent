"""One-off backfill: attribute source documents to pre-tracking concepts.

Rule (strict, explainable, no guessing): a concept with document_id NULL is
attributed to a document IFF its exact name occurs as a whole word/phrase
(case-insensitive) in chunks of EXACTLY ONE document of the same project.
Ambiguous (0 or 2+ documents) concepts are left unattributed.

Usage:
  docker exec ai-study-companion-backend-1 python /code/scripts/attribute_concept_sources.py [--apply]
Default is dry-run (report only). --apply writes the matches.
"""
import re
import sys
from collections import defaultdict

from app.db.session import SessionLocal
import app.db.base  # noqa: F401 — register models
from app.db.models.assessment import Concept
from app.db.models.document import Document, DocumentChunk

DRY_RUN = "--apply" not in sys.argv


def word_pattern(name: str) -> re.Pattern:
    # Whole-phrase, case-insensitive; lookarounds (not \b) so names ending
    # in punctuation like ")" still match correctly.
    return re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.IGNORECASE)


def main() -> int:
    db = SessionLocal()
    try:
        concepts = db.query(Concept).filter(Concept.document_id.is_(None)).all()
        if not concepts:
            print("No unattributed concepts. Nothing to do.")
            return 0

        by_project = defaultdict(list)
        for c in concepts:
            by_project[c.project_id].append(c)

        attributed, ambiguous, missing = [], [], []
        for pid, plist in by_project.items():
            chunks = db.query(DocumentChunk).filter(DocumentChunk.project_id == pid).all()
            docs = {d.id: d for d in db.query(Document).filter(Document.project_id == pid).all()}
            text_by_doc = defaultdict(str)
            for ch in chunks:
                text_by_doc[ch.document_id] += "\n" + (ch.content or "")
            for c in plist:
                try:
                    rx = word_pattern(c.name)
                except re.error:
                    missing.append((c, "bad-pattern"))
                    continue
                hits = [did for did, text in text_by_doc.items() if text and rx.search(text)]
                # Ignore hits in documents that no longer exist (defensive).
                hits = [did for did in hits if did in docs]
                if len(hits) == 1:
                    attributed.append((c, docs[hits[0]]))
                elif len(hits) == 0:
                    missing.append((c, "no-match"))
                else:
                    missing.append((c, f"ambiguous-{len(hits)}-docs"))

        print(f"Unattributed concepts scanned: {len(concepts)}")
        print(f"  Unique single-document matches: {len(attributed)}")
        print(f"  Left unattributed: {len(missing)}")
        for c, doc in attributed:
            print(f"  MATCH  {c.name!r} -> {doc.file_name!r}")
        amb = [(c, r) for c, r in missing if r != "no-match"]
        if amb:
            print(f"  Ambiguous/no-match examples:")
            for c, r in amb[:10]:
                print(f"    SKIP ({r}) {c.name!r}")

        if DRY_RUN:
            print("\nDry run — no writes. Re-run with --apply to stamp matches.")
            return 0

        for c, doc in attributed:
            row = db.get(Concept, c.id)
            if row is not None and row.document_id is None:
                row.document_id = doc.id
        db.commit()
        print(f"\nApplied: {len(attributed)} concepts attributed.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
