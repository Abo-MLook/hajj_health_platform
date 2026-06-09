from unittest import TestCase
from unittest.mock import MagicMock, patch

from apps.pilgrims.extraction.image_extractor import OCR_LANGUAGES, extract_text_from_image


class ExtractTextFromImageTests(TestCase):
    @patch("apps.pilgrims.extraction.image_extractor.pytesseract.image_to_string")
    @patch("apps.pilgrims.extraction.image_extractor.Image.open")
    def test_runs_ocr_with_detected_language(self, mock_image_open, mock_image_to_string):
        mock_image = MagicMock()
        mock_image_open.return_value.__enter__.return_value = mock_image
        mock_image_to_string.return_value = "Patient: John Smith"

        result = extract_text_from_image("fake.png")

        # assert using whatever language was detected at startup (eng or ara+eng)
        mock_image_to_string.assert_called_once_with(mock_image, lang=OCR_LANGUAGES)
        self.assertEqual(result, "Patient: John Smith")

    @patch("apps.pilgrims.extraction.image_extractor.pytesseract.image_to_string")
    @patch("apps.pilgrims.extraction.image_extractor.Image.open")
    def test_strips_whitespace_from_result(self, mock_image_open, mock_image_to_string):
        mock_image = MagicMock()
        mock_image_open.return_value.__enter__.return_value = mock_image
        mock_image_to_string.return_value = "  \n  Patient: John Smith  \n  "

        result = extract_text_from_image("fake.png")

        self.assertEqual(result, "Patient: John Smith")

    @patch("apps.pilgrims.extraction.image_extractor.Image.open")
    def test_returns_empty_string_on_failure(self, mock_image_open):
        mock_image_open.side_effect = Exception("not an image")

        result = extract_text_from_image("broken.png")

        self.assertEqual(result, "")

    @patch("apps.pilgrims.extraction.image_extractor.pytesseract.image_to_string")
    @patch("apps.pilgrims.extraction.image_extractor.Image.open")
    def test_returns_empty_string_when_ocr_raises(self, mock_image_open, mock_image_to_string):
        mock_image = MagicMock()
        mock_image_open.return_value.__enter__.return_value = mock_image
        mock_image_to_string.side_effect = Exception("tesseract error")

        result = extract_text_from_image("fake.png")

        self.assertEqual(result, "")

    def test_ocr_language_is_string(self):
        self.assertIsInstance(OCR_LANGUAGES, str)
        self.assertIn("eng", OCR_LANGUAGES)
