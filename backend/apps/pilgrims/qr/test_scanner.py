from unittest import TestCase
from unittest.mock import MagicMock, patch

from apps.pilgrims.qr.scanner import decode_patient_id


class DecodePatientIdTests(TestCase):
    @patch("apps.pilgrims.qr.scanner.decode")
    @patch("apps.pilgrims.qr.scanner.Image.open")
    def test_returns_decoded_patient_id(self, mock_open, mock_decode):
        mock_open.return_value.__enter__.return_value = MagicMock()
        mock_decode.return_value = [MagicMock(data=b"ABC123DEF456")]

        result = decode_patient_id("qr.png")

        self.assertEqual(result, "ABC123DEF456")

    @patch("apps.pilgrims.qr.scanner.decode")
    @patch("apps.pilgrims.qr.scanner.Image.open")
    def test_returns_none_when_no_qr_code_found(self, mock_open, mock_decode):
        mock_open.return_value.__enter__.return_value = MagicMock()
        mock_decode.return_value = []

        result = decode_patient_id("plain_image.png")

        self.assertIsNone(result)

    @patch("apps.pilgrims.qr.scanner.Image.open")
    def test_returns_none_when_image_cannot_be_opened(self, mock_open):
        mock_open.side_effect = Exception("not an image")

        result = decode_patient_id("broken.png")

        self.assertIsNone(result)
