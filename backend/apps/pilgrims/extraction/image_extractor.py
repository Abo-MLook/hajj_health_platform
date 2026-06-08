import logging
import os
import shutil

import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

OCR_LANGUAGES = "ara+eng"

# Fallback path for Windows installs where the Tesseract installer
# doesn't add itself to PATH (a common issue with the UB-Mannheim build).
WINDOWS_FALLBACK_TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if not shutil.which("tesseract") and os.path.isfile(WINDOWS_FALLBACK_TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = WINDOWS_FALLBACK_TESSERACT_CMD


def extract_text_from_image(file_path):
    """Extract raw text from an image file (JPG/JPEG/PNG) using pytesseract OCR.

    Recognizes both Arabic and English text. Returns an empty string
    if the file can't be opened or OCR fails.
    """
    try:
        with Image.open(file_path) as image:
            return pytesseract.image_to_string(image, lang=OCR_LANGUAGES).strip()
    except Exception:
        logger.exception("Failed to extract text from image: %s", file_path)
        return ""
