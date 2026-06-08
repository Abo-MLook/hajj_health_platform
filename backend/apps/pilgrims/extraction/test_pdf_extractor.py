from unittest import TestCase
from unittest.mock import MagicMock, patch

from apps.pilgrims.extraction.pdf_extractor import extract_text_from_pdf


class ExtractTextFromPdfTests(TestCase):
    @patch("apps.pilgrims.extraction.pdf_extractor.pdfplumber.open")
    def test_joins_text_from_all_pages(self, mock_open):
        page_one = MagicMock()
        page_one.extract_text.return_value = "Page one text"
        page_two = MagicMock()
        page_two.extract_text.return_value = "Page two text"

        mock_pdf = MagicMock()
        mock_pdf.pages = [page_one, page_two]
        mock_open.return_value.__enter__.return_value = mock_pdf

        result = extract_text_from_pdf("fake.pdf")

        self.assertEqual(result, "Page one text\nPage two text")

    @patch("apps.pilgrims.extraction.pdf_extractor.pdfplumber.open")
    def test_returns_empty_string_for_corrupted_file(self, mock_open):
        mock_open.side_effect = Exception("corrupted PDF")

        result = extract_text_from_pdf("broken.pdf")

        self.assertEqual(result, "")
