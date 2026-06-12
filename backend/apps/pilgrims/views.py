import logging
import os
import tempfile
import uuid

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .extraction.image_extractor import extract_text_from_image
from .extraction.pdf_extractor import extract_text_from_pdf
from .models import MedicalDocument, Pilgrim

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}


@require_http_methods(["GET", "POST"])
def upload_test(request):
    if request.method == "POST":
        return _handle_upload(request)
    return render(request, "upload_test.html")


def _handle_upload(request):
    patient_name = request.POST.get("patient_name", "").strip()
    uploaded_file = request.FILES.get("file")

    if not uploaded_file:
        return JsonResponse({"error": "Please select a file to upload."}, status=400)

    ext = uploaded_file.name.rsplit(".", 1)[-1].lower() if "." in uploaded_file.name else ""
    if ext not in ALLOWED_EXTENSIONS:
        return JsonResponse(
            {"error": f"File type .{ext} is not allowed. Use PDF, JPG, JPEG, or PNG."},
            status=400,
        )

    # Each upload creates a new pilgrim with a unique auto-generated passport number.
    # Use typed name as placeholder; will be overwritten by AI-extracted name if blank.
    passport_number = f"AUTO-{uuid.uuid4().hex[:8].upper()}"
    pilgrim = Pilgrim.objects.create(
        full_name=patient_name or f"Patient-{passport_number[-6:]}",
        passport_number=passport_number,
    )

    # Extract text now while the file is still in memory (before Cloudinary upload).
    # The signal-triggered pipeline will reuse this text if cloud download is unavailable.
    pre_extracted_text = _extract_text_from_memory(uploaded_file, ext)
    uploaded_file.seek(0)  # Reset so Django can upload the full file to Cloudinary

    try:
        document = MedicalDocument.objects.create(
            pilgrim=pilgrim,
            file=uploaded_file,
            original_filename=uploaded_file.name,
            file_type=ext,
            extracted_text=pre_extracted_text,
        )
    except Exception:
        logger.exception("Failed to create MedicalDocument for pilgrim %s", pilgrim.pk)
        return JsonResponse({"error": "Upload failed. Please try again."}, status=500)

    # Signal ran synchronously — document already has pipeline results,
    # and the pipeline may have filled the pilgrim's demographic fields
    document.refresh_from_db()
    pilgrim.refresh_from_db()

    # If the user didn't type a name, use the one the AI extracted from the document
    if not patient_name and document.extracted_json:
        extracted_name = (document.extracted_json.get("patient_name") or "").strip()
        if extracted_name:
            pilgrim.full_name = extracted_name
            pilgrim.save(update_fields=["full_name"])

    health_profile_data = None
    try:
        hp = pilgrim.health_profile
        health_profile_data = {
            "status": hp.status,
            "confidence_score": hp.confidence_score,
            "diseases": hp.diseases_text,
            "medications": hp.medications_text,
            "allergies": hp.allergies_text,
            "vaccinations": hp.vaccinations_text,
        }
    except Exception:
        pass

    return JsonResponse({
        "success": True,
        "document_id": document.pk,
        "pilgrim_name": pilgrim.full_name,
        "pilgrim": {
            "full_name": pilgrim.full_name,
            "date_of_birth": pilgrim.date_of_birth.isoformat() if pilgrim.date_of_birth else None,
            "age": pilgrim.age,
            "gender": pilgrim.gender or None,
            "nationality": pilgrim.nationality or None,
        },
        "filename": document.original_filename,
        "file_url": document.file.url,
        "extracted_text_preview": (document.extracted_text or "")[:600] or None,
        "extracted_json": document.extracted_json,
        "confidence_score": document.confidence_score,
        "status": document.status,
        "health_profile": health_profile_data,
    })


def _extract_text_from_memory(uploaded_file, ext):
    """Extract text from an uploaded file while it is still in memory,
    before it is sent to cloud storage. Returns empty string on any failure.
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp_path = tmp.name
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)

        if ext == "pdf":
            return extract_text_from_pdf(tmp_path)
        if ext in ("jpg", "jpeg", "png"):
            return extract_text_from_image(tmp_path)
        return ""
    except Exception:
        logger.exception("Pre-extraction failed for %s", uploaded_file.name)
        return ""
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
