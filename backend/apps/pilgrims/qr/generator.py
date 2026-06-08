import qrcode


def generate_qr_code_image(pilgrim):
    """Build a QR code image that encodes a pilgrim's patient_id only."""
    return qrcode.make(pilgrim.patient_id)
