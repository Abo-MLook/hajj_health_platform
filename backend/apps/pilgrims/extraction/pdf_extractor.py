import logging

import pdfplumber

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path):
    """Extract raw text from a PDF file using pdfplumber.

    Returns an empty string if the file is corrupted, empty,
    or contains no extractable text.
    """
    try:
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts).strip()
    except Exception:
        logger.exception("Failed to extract text from PDF: %s", file_path)
        return ""
