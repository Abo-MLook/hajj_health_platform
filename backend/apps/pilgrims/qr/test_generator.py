from unittest import TestCase

from pyzbar.pyzbar import decode

from apps.pilgrims.models import Pilgrim
from apps.pilgrims.qr.generator import generate_qr_code_image


class GenerateQrCodeImageTests(TestCase):
    def test_generated_image_encodes_patient_id(self):
        pilgrim = Pilgrim(full_name="Test Pilgrim", passport_number="P-QR-1")

        image = generate_qr_code_image(pilgrim)
        results = decode(image.convert("RGB"))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].data.decode("utf-8"), pilgrim.patient_id)
