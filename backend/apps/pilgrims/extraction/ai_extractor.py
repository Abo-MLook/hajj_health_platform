import json
import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

EXTRACTION_PROMPT = """You are a medical data extraction assistant for a Hajj health platform.

Read the medical document text below and extract structured data as JSON
with exactly these keys:
- "patient_name": the full name of the patient as written in the document (string, or null if not found)
- "date_of_birth": the patient's date of birth in YYYY-MM-DD format (string, or null if not found).
  If only an age is stated (e.g. "Age: 58"), estimate the birth year and use January 1st (e.g. "1968-01-01").
- "gender": "male" or "female" (string, or null if not stated)
- "nationality": the patient's nationality or country (string, or null if not found)
- "diseases": a list of chronic disease names (strings)
- "medications": a list of objects, each with "name", "dose", and "frequency"
- "allergies": a list of allergy names (strings)
- "vaccinations": a list of vaccination names (strings)
- "height": patient's height in cm (float, or null if not found)
- "weight": patient's weight in kg (float, or null if not found)
- "systolic_bp": patient's systolic blood pressure (integer, or null if not found)
- "diastolic_bp": patient's diastolic blood pressure (integer, or null if not found)
- "total_cholesterol": patient's total cholesterol (integer, or null if not found)
- "hdl_cholesterol": patient's HDL cholesterol (integer, or null if not found)
- "smoker": boolean true if patient smokes, false if non-smoker, null if not found
- "oxygen_usage": boolean true if patient uses oxygen, false if not, null if not found

If a field is not mentioned in the text, return null for the single-value fields
(patient_name, date_of_birth, gender, nationality, height, weight, systolic_bp, diastolic_bp, total_cholesterol, hdl_cholesterol, smoker, oxygen_usage) or an empty list for the others.
Respond with ONLY the JSON object — no explanation, no markdown formatting.

Document text:
---
{text}
---
"""


def _get_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set in the environment.")
    return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")


def _parse_json_response(raw_response):
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


def extract_structured_data(raw_text):
    """Send raw medical document text to Groq and return structured medical data.

    Returns a dict with keys: patient_name, date_of_birth, gender, nationality,
    diseases, medications, allergies, vaccinations.
    Returns None if the API call fails or the response isn't valid JSON.
    """
    if not raw_text or not raw_text.strip():
        return None

    try:
        client = _get_client()
        model_name = os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": EXTRACTION_PROMPT.format(text=raw_text)}
            ],
        )
        return _parse_json_response(response.choices[0].message.content)
    except Exception:
        logger.exception("Failed to extract structured data via Groq")
        return None
