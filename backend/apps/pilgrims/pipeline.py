import logging

from .agent import review_agent
from .extraction.confidence import score_document
from .extraction.extractor import extract_text_from_document
from .extraction.json_extractor import extract_json_from_document
from .merging import merge_health_profile

logger = logging.getLogger(__name__)


def run_pipeline(document):
    """Run the full processing pipeline for a newly uploaded MedicalDocument.

    Steps (each saves its results to the document/profile immediately):
      1. Extract raw text from the file (PDF or image OCR)
      2. Send the text to Gemini and save structured medical JSON
      3. Calculate a confidence score and review status
      4. Merge all documents into the pilgrim's unified HealthProfile

    Returns a summary dict — useful for logging, tests, and future task queues.
    """
    logger.info("Pipeline started for document %s (pilgrim %s)", document.pk, document.pilgrim_id)

    extract_text_from_document(document)
    extract_json_from_document(document)
    score_document(document)

    if document.confidence_score < 75:
        review_agent(document)

    health_profile = merge_health_profile(document.pilgrim)

    document.refresh_from_db()

    summary = {
        "extracted_text_length": len(document.extracted_text or ""),
        "extracted_json": document.extracted_json,
        "confidence_score": document.confidence_score,
        "status": document.status,
        "health_profile_status": health_profile.status,
    }

    logger.info("Pipeline complete for document %s: %s", document.pk, summary)
    return summary
