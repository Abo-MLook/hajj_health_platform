import json
import logging
import os

import google.generativeai as genai

logger = logging.getLogger(__name__)

GEMINI_MODEL_NAME = "gemini-3.5-flash"

EXTRACTION_PROMPT = """You are a medical data extraction assistant for a Hajj health platform.

Read the medical document text below and extract structured data as JSON
with exactly these keys:
- "diseases": a list of chronic disease names (strings)
- "medications": a list of objects, each with "name", "dose", and "frequency"
- "allergies": a list of allergy names (strings)
- "vaccinations": a list of vaccination names (strings)

If a field is not mentioned in the text, return an empty list for it.
Respond with ONLY the JSON object — no explanation, no markdown formatting.

Document text:
---
{text}
---
"""


def _get_model():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(GEMINI_MODEL_NAME)


def _parse_json_response(raw_response):
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


def extract_structured_data(raw_text):
    """Send raw medical document text to Gemini and return structured medical data.

    Returns a dict with keys: diseases, medications, allergies, vaccinations.
    Returns None if the AI call fails or the response isn't valid JSON.
    """
    if not raw_text or not raw_text.strip():
        return None

    try:
        model = _get_model()
        response = model.generate_content(EXTRACTION_PROMPT.format(text=raw_text))
        return _parse_json_response(response.text)
    except Exception:
        logger.exception("Failed to extract structured data via Gemini")
        return None
