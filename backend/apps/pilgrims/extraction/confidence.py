import os

CONFIDENCE_QR_VERIFIED = 100
CONFIDENCE_PDF = 75
CONFIDENCE_IMAGE = 50

PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def calculate_confidence_score(document):
    """Estimate how trustworthy a document's extracted data is, based on its source.

    QR-verified documents (Stage 8) will score highest, clear PDFs score
    medium/high, and images (OCR-based, more error-prone) score medium.
    """
    extension = os.path.splitext(document.file.name)[1].lower()
    if extension in PDF_EXTENSIONS:
        return CONFIDENCE_PDF
    if extension in IMAGE_EXTENSIONS:
        return CONFIDENCE_IMAGE
    return 0


def score_document(document):
    """Calculate and persist a MedicalDocument's confidence_score and status.

    A document is flagged "needs_review" when extraction did not produce
    usable text or structured data, regardless of its source-based score.
    """
    score = calculate_confidence_score(document)

    if not document.extracted_text.strip() or document.extracted_json is None:
        status = "needs_review"
    else:
        status = "pending"

    document.confidence_score = score
    document.status = status
    document.save(update_fields=["confidence_score", "status", "updated_at"])
    return score, status
