import os
import requests
from dotenv import load_dotenv

load_dotenv()

COLIVARA_API_KEY = os.getenv("COLIVARA_API_KEY")
OCR_API_KEY = os.getenv("OCR_API_KEY")

COLIVARA_BASE_URL = "https://api.colivara.com/v1"
OCR_BASE_URL = "https://api.dummy-ocr.com/v1"

def index_pdf_to_colivara(pdf_file_path: str, collection_name: str = "default"):
    """
    Uploads and indexes a PDF to ColiVara Visual RAG.
    """
    headers = {"Authorization": f"Bearer {COLIVARA_API_KEY}"}
    # TODO: Implement actual requests.post to COLIVARA_BASE_URL when ready.
    print(f"[DEMO] Indexing {pdf_file_path} to ColiVara collection '{collection_name}'...")
    return {"status": "success", "document_id": "dummy_doc_123"}

def search_colivara(query: str, collection_name: str = "default"):
    """
    Searches indexed PDFs in ColiVara and returns relevant page images/links.
    """
    headers = {"Authorization": f"Bearer {COLIVARA_API_KEY}"}
    # TODO: Implement actual requests.get to COLIVARA_BASE_URL when ready.
    print(f"[DEMO] Searching ColiVara for: '{query}'...")
    return [
        {"page_id": "page_1", "image_url": "https://dummy.image.com/page1.png", "document": "doc_123"},
        {"page_id": "page_5", "image_url": "https://dummy.image.com/page5.png", "document": "doc_123"}
    ]

def ocr_colivara_pages(colivara_results: list):
    """
    Takes the relevant pages returned by ColiVara and sends them to an OCR API
    to extract text.
    """
    headers = {"Authorization": f"Bearer {OCR_API_KEY}"}
    extracted_texts = []

    # TODO: Implement actual requests.post to OCR_BASE_URL sending the image_url when ready.
    for page in colivara_results:
        print(f"[DEMO] Running OCR on page {page['page_id']} from {page['image_url']}...")
        dummy_text = f"This is the extracted text for page {page['page_id']}. It contains relevant context for the user's query."

        extracted_texts.append({
            "page_id": page["page_id"],
            "source_document": page["document"],
            "extracted_text": dummy_text
        })

    return extracted_texts

def retrieve_and_extract_context(query: str):
    """
    Main orchestrator function to replace my existing retrieval logic.
    """
    # 1. Search ColiVara
    relevant_pages = search_colivara(query)

    # 2. OCR the results
    ocr_results = ocr_colivara_pages(relevant_pages)

    # 3. Format for Existing LLM
    context_string = "\n\n".join([f"Source: {res['source_document']} (Page: {res['page_id']})\nContent: {res['extracted_text']}" for res in ocr_results])

    return context_string, ocr_results
