import pymupdf


def parse_pdf(file_path: str) -> list[dict]:
    doc = pymupdf.open(file_path)
    try:
        return [
            {"page_number": i + 1, "text": page.get_text()}
            for i, page in enumerate(doc)
        ]
    finally:
        doc.close()
