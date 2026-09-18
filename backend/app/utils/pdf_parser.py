import io

import pymupdf
from loguru import logger
from PIL import Image

try:
    import pytesseract
except ImportError:  # pragma: no cover - missing dep is handled gracefully
    pytesseract = None

# Render resolution for the OCR fallback. 300 DPI is the standard
# tradeoff between Tesseract accuracy and render time/memory.
OCR_DPI = 300


def _ocr_page(page: pymupdf.Page) -> str:
    """Render a page with no text layer to an image and OCR it.

    Returns "" on any failure (missing binary, bad image, ...) so one
    unreadable page never fails the whole document.
    """
    if pytesseract is None:
        logger.warning("pytesseract not installed; skipping OCR for a text-less page")
        return ""
    try:
        pixmap = page.get_pixmap(dpi=OCR_DPI)
        img = Image.open(io.BytesIO(pixmap.tobytes("png")))
        return pytesseract.image_to_string(img) or ""
    except Exception as e:
        logger.warning(f"OCR failed for a page: {e}")
        return ""


def parse_pdf(file_path: str) -> list[dict]:
    """Extract per-page text from a PDF, with OCR fallback for scans.

    Each record is {"page_number": int, "text": str, "source": str} where
    source is "text" (embedded text layer), "ocr" (Tesseract fallback),
    or "empty" (nothing extractable on that page).

    Raises RuntimeError with a user-actionable message for missing,
    empty, encrypted, or corrupt files (caller stores it on Document.error).
    """
    import os

    if not file_path or not os.path.exists(file_path):
        raise RuntimeError(
            "Upload file not found on worker "
            f"(path={file_path!r}). Web and worker do not share storage: "
            "mount the SAME Railway volume into both services and set "
            "UPLOAD_DIR=/data/uploads on both."
        )
    try:
        if os.path.getsize(file_path) == 0:
            raise RuntimeError("Uploaded file is empty (0 bytes). Please re-upload the PDF.")
    except OSError as e:
        raise RuntimeError(f"Cannot read uploaded file: {e}")
    try:
        doc = pymupdf.open(file_path)
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypted" in msg:
            raise RuntimeError("PDF is password-protected. Remove the password and re-upload.")
        raise RuntimeError(f"Cannot open PDF (corrupt or not a real PDF): {e}")
    if getattr(doc, "is_encrypted", False) and getattr(doc, "needs_pass", True):
        try:
            doc.close()
        except Exception:
            pass
        raise RuntimeError("PDF is password-protected. Remove the password and re-upload.")
    if len(doc) == 0:
        try:
            doc.close()
        except Exception:
            pass
        raise RuntimeError("PDF has no pages.")
    try:
        pages: list[dict] = []
        for i, page in enumerate(doc):
            text = page.get_text() or ""
            source = "text"
            if not text.strip():
                text = _ocr_page(page)
                source = "ocr" if text.strip() else "empty"
            pages.append({"page_number": i + 1, "text": text, "source": source})
        return pages
    finally:
        doc.close()
