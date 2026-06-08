from unittest import TestCase
from unittest.mock import MagicMock, patch

from apps.pilgrims.extraction.image_extractor import extract_text_from_image


class ExtractTextFromImageTests(TestCase):
    @patch("apps.pilgrims.extraction.image_extractor.pytesseract.image_to_string")
    @patch("apps.pilgrims.extraction.image_extractor.Image.open")
    def test_runs_ocr_with_arabic_and_english(self, mock_image_open, mock_image_to_string):
        mock_image = MagicMock()
        mock_image_open.return_value.__enter__.return_value = mock_image
        mock_image_to_string.return_value = "Hello مرحبا"

        result = extract_text_from_image("fake.png")

        mock_image_to_string.assert_called_once_with(mock_image, lang="ara+eng")
        self.assertEqual(result, "Hello مرحبا")

    @patch("apps.pilgrims.extraction.image_extractor.Image.open")
    def test_returns_empty_string_on_failure(self, mock_image_open):
        mock_image_open.side_effect = Exception("not an image")

        result = extract_text_from_image("broken.png")

        self.assertEqual(result, "")
