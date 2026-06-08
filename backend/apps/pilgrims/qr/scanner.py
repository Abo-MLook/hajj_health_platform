import logging

from PIL import Image
from pyzbar.pyzbar import decode

logger = logging.getLogger(__name__)


def decode_patient_id(file_path):
    """Read a QR code image and return the patient_id it encodes.

    Returns None if the file can't be opened, contains no QR code,
    or decoding otherwise fails.
    """
    try:
        with Image.open(file_path) as image:
            results = decode(image)
    except Exception:
        logger.exception("Failed to decode QR code from image: %s", file_path)
        return None

    if not results:
        return None

    return results[0].data.decode("utf-8").strip()
