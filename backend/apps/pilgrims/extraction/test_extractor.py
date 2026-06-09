import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.pilgrims.extraction.extractor import extract_text_from_document
from apps.pilgrims.models import MedicalDocument, Pilgrim

TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="pilgrims_extraction_tests_")


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class ExtractTextFromDocumentTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        patcher = patch("apps.pilgrims.signals.run_pipeline")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pilgrim = Pilgrim.objects.create(full_name="Test Pilgrim", passport_number="P-EXTRACT-1")

    @patch("apps.pilgrims.extraction.extractor.extract_text_from_pdf")
    def test_routes_pdf_files_to_pdf_extractor_and_saves_result(self, mock_extract_pdf):
        mock_extract_pdf.return_value = "extracted pdf text"
        document = MedicalDocument.objects.create(
            pilgrim=self.pilgrim,
            file=SimpleUploadedFile("report.pdf", b"%PDF-1.4 fake content", content_type="application/pdf"),
        )

        result = extract_text_from_document(document)

        mock_extract_pdf.assert_called_once_with(document.file.path)
        self.assertEqual(result, "extracted pdf text")
        document.refresh_from_db()
        self.assertEqual(document.extracted_text, "extracted pdf text")

    @patch("apps.pilgrims.extraction.extractor.extract_text_from_image")
    def test_routes_image_files_to_image_extractor_and_saves_result(self, mock_extract_image):
        mock_extract_image.return_value = "extracted image text"
        document = MedicalDocument.objects.create(
            pilgrim=self.pilgrim,
            file=SimpleUploadedFile("scan.jpg", b"fake image bytes", content_type="image/jpeg"),
        )

        result = extract_text_from_document(document)

        mock_extract_image.assert_called_once_with(document.file.path)
        self.assertEqual(result, "extracted image text")
        document.refresh_from_db()
        self.assertEqual(document.extracted_text, "extracted image text")

    @patch("apps.pilgrims.extraction.extractor.extract_text_from_pdf")
    @patch("apps.pilgrims.extraction.extractor.extract_text_from_image")
    def test_skips_extraction_when_text_already_present(self, mock_image, mock_pdf):
        """If extracted_text is already populated, skip re-extraction entirely."""
        document = MedicalDocument.objects.create(
            pilgrim=self.pilgrim,
            file=SimpleUploadedFile("scan.jpg", b"fake image bytes", content_type="image/jpeg"),
            extracted_text="pre-extracted text from view",
        )

        result = extract_text_from_document(document)

        mock_image.assert_not_called()
        mock_pdf.assert_not_called()
        self.assertEqual(result, "pre-extracted text from view")

    @patch("apps.pilgrims.extraction.extractor.extract_text_from_pdf")
    def test_extracts_when_text_is_empty_string(self, mock_extract_pdf):
        """Empty string should trigger re-extraction, not count as pre-extracted."""
        mock_extract_pdf.return_value = "fresh extraction"
        document = MedicalDocument.objects.create(
            pilgrim=self.pilgrim,
            file=SimpleUploadedFile("report.pdf", b"%PDF-1.4", content_type="application/pdf"),
            extracted_text="",
        )

        result = extract_text_from_document(document)

        mock_extract_pdf.assert_called_once()
        self.assertEqual(result, "fresh extraction")
