import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.pilgrims.extraction.json_extractor import extract_json_from_document
from apps.pilgrims.models import MedicalDocument, Pilgrim

TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="pilgrims_json_extraction_tests_")

STRUCTURED_DATA = {
    "diseases": ["Type 2 Diabetes"],
    "medications": [{"name": "Metformin", "dose": "500mg", "frequency": "twice daily"}],
    "allergies": ["Penicillin"],
    "vaccinations": ["COVID-19"],
}


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class ExtractJsonFromDocumentTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        patcher = patch("apps.pilgrims.signals.run_pipeline")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pilgrim = Pilgrim.objects.create(full_name="Test Pilgrim", passport_number="P-JSON-1")
        self.document = MedicalDocument.objects.create(
            pilgrim=self.pilgrim,
            file=SimpleUploadedFile("report.pdf", b"%PDF-1.4 fake content", content_type="application/pdf"),
            extracted_text="Patient has Type 2 Diabetes, takes Metformin 500mg twice daily...",
        )

    @patch("apps.pilgrims.extraction.json_extractor.extract_structured_data")
    def test_saves_structured_data_to_extracted_json(self, mock_extract):
        mock_extract.return_value = STRUCTURED_DATA

        result = extract_json_from_document(self.document)

        mock_extract.assert_called_once_with(self.document.extracted_text)
        self.assertEqual(result, STRUCTURED_DATA)
        self.document.refresh_from_db()
        self.assertEqual(self.document.extracted_json, STRUCTURED_DATA)

    @patch("apps.pilgrims.extraction.json_extractor.extract_structured_data")
    def test_saves_none_when_extraction_fails(self, mock_extract):
        mock_extract.return_value = None

        result = extract_json_from_document(self.document)

        self.assertIsNone(result)
        self.document.refresh_from_db()
        self.assertIsNone(self.document.extracted_json)
