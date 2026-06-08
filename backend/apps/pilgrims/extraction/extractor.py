import logging
import os
import tempfile

from .image_extractor import extract_text_from_image
from .pdf_extractor import extract_text_from_pdf

logger = logging.getLogger(__name__)

PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _local_path(document):
    """Return (path, is_temp) for the document file.

    For local filesystem storage, returns the existing on-disk path and
    is_temp=False (nothing to clean up).

    For cloud storage (Cloudinary, S3, etc.), .path raises NotImplementedError
    or ValueError, so we stream the file through Django's storage API into a
    temp file and return that path with is_temp=True — caller must delete it.
    """
    try:
        return document.file.path, False
    except (NotImplementedError, ValueError):
        pass

    extension = os.path.splitext(document.file.name)[1].lower()
    tmp = tempfile.NamedTemporaryFile(suffix=extension or ".tmp", delete=False)
    try:
        logger.debug("Streaming %s from cloud storage for extraction", document.file.name)
        document.file.open("rb")
        try:
            tmp.write(document.file.read())
        finally:
            document.file.close()
    finally:
        tmp.close()
    return tmp.name, True


def extract_text_from_document(document):
    """Detect a MedicalDocument's file type, extract its raw text,
    save it to MedicalDocument.extracted_text, and return the text.

    Works with local filesystem storage and cloud storage (Cloudinary).
    For cloud storage where download is restricted, if extracted_text is
    already populated (pre-extracted at upload time in the view), this
    function keeps the existing text rather than overwriting with empty.
    """
    try:
        file_path, is_temp = _local_path(document)
    except Exception:
        if document.extracted_text:
            logger.debug(
                "Cannot download document %s from cloud storage — keeping pre-extracted text.",
                document.pk,
            )
            return document.extracted_text
        logger.warning(
            "Cannot download document %s from cloud storage and no pre-extracted text available.",
            document.pk,
        )
        return ""

    extension = os.path.splitext(document.file.name)[1].lower()
    try:
        if extension in PDF_EXTENSIONS:
            text = extract_text_from_pdf(file_path)
        elif extension in IMAGE_EXTENSIONS:
            text = extract_text_from_image(file_path)
        else:
            text = ""
    finally:
        if is_temp:
            os.unlink(file_path)

    document.extracted_text = text
    document.save(update_fields=["extracted_text", "updated_at"])
    return text
