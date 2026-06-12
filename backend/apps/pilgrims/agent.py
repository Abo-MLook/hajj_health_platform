import json
import logging
import os

from groq import Groq

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"
MAX_ATTEMPTS = 3

REVIEW_PROMPT = """You are a medical data correction specialist reviewing text extracted via OCR from a medical document image.

OCR engines make common mistakes on medical documents:
- Wrong doses: "50mg" instead of "500mg", "1mg" instead of "10mg"
- Misspelled drug names: "Penicelin" instead of "Penicillin", "Metfomin" instead of "Metformin"
- Misspelled conditions: "Diabetis" instead of "Diabetes", "Hypertencion" instead of "Hypertension"
- Wrong frequency: "twise daily" instead of "twice daily", "daly" instead of "daily"
- Merged or split words: "twicedaily", "Insuln Glargine"

Below is the raw OCR text. Read it carefully, correct all OCR errors you find, then extract the medical data.

Return ONLY a JSON object with exactly these keys:
- "patient_name": the patient's full name, spelling corrected (string, or null if not found)
- "date_of_birth": the patient's date of birth in YYYY-MM-DD format (string, or null if not found)
- "gender": "male" or "female" (string, or null if not stated)
- "nationality": the patient's nationality or country (string, or null if not found)
- "diseases": list of corrected chronic disease names (strings)
- "medications": list of objects, each with "name", "dose", "frequency" (all corrected)
- "allergies": list of corrected allergy names (strings)
- "vaccinations": list of corrected vaccination names (strings)
- "corrections_made": list of strings describing each correction, e.g. ["50mg corrected to 500mg", "Penicelin corrected to Penicillin"]

If no corrections were needed for a field, still extract it correctly.
If corrections_made is empty, return an empty list.

Raw OCR text:
---
{text}
---
"""


def _get_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set in the environment.")
    return Groq(api_key=api_key)


def _parse_response(raw):
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


def _has_meaningful_data(data):
    return (
        data.get("diseases") or
        data.get("medications") or
        data.get("allergies") or
        data.get("vaccinations")
    )


def _preserve_identity_fields(old_json, new_data):
    """Keep identity fields from the original extraction when the review
    response omits them, so corrections never erase the patient's identity.
    """
    if not old_json:
        return
    for key in ("patient_name", "date_of_birth", "gender", "nationality"):
        if not new_data.get(key) and old_json.get(key):
            new_data[key] = old_json[key]


def _corrections_differ(old_json, new_data):
    if not old_json:
        return True
    for key in ("diseases", "medications", "allergies", "vaccinations"):
        if old_json.get(key) != new_data.get(key):
            return True
    return False


def review_agent(document):
    """Review and correct OCR extraction errors in a low-confidence document.

    Only runs when confidence_score < 75 (image-sourced documents).
    Sends the raw OCR text to Groq with a correction-focused prompt,
    retrying up to 3 times. Updates extracted_json and sets status on success.

    Returns a summary dict with corrections_made, final_status, improved.
    """
    if document.confidence_score >= 75:
        return {
            "corrections_made": [],
            "final_status": document.status,
            "improved": False,
            "attempts": 0,
            "skipped": True,
        }

    if not document.extracted_text or not document.extracted_text.strip():
        logger.warning("Review agent: document %s has no extracted text to review.", document.pk)
        document.status = "needs_review"
        document.save(update_fields=["status", "updated_at"])
        return {
            "corrections_made": [],
            "final_status": "needs_review",
            "improved": False,
            "attempts": 0,
            "skipped": False,
        }

    client = _get_client()
    prompt = REVIEW_PROMPT.format(text=document.extracted_text)
    old_json = document.extracted_json

    for attempt in range(1, MAX_ATTEMPTS + 1):
        logger.info("Review agent: attempt %d/%d for document %s.", attempt, MAX_ATTEMPTS, document.pk)
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            data = _parse_response(response.choices[0].message.content)

            if _has_meaningful_data(data):
                corrections = data.pop("corrections_made", [])
                _preserve_identity_fields(old_json, data)
                improved = _corrections_differ(old_json, data)

                document.extracted_json = data
                document.status = "approved"
                document.save(update_fields=["extracted_json", "status", "updated_at"])

                logger.info(
                    "Review agent: document %s approved after %d attempt(s). Corrections: %s",
                    document.pk, attempt, corrections,
                )
                return {
                    "corrections_made": corrections,
                    "final_status": "approved",
                    "improved": improved,
                    "attempts": attempt,
                    "skipped": False,
                }

            logger.warning("Review agent: attempt %d returned no meaningful data.", attempt)

        except Exception:
            logger.exception("Review agent: attempt %d failed for document %s.", attempt, document.pk)

    logger.warning(
        "Review agent: all %d attempts failed for document %s — flagging for human review.",
        MAX_ATTEMPTS, document.pk,
    )
    document.status = "needs_review"
    document.save(update_fields=["status", "updated_at"])
    return {
        "corrections_made": [],
        "final_status": "needs_review",
        "improved": False,
        "attempts": MAX_ATTEMPTS,
        "skipped": False,
    }
