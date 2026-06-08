import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.pilgrims.extraction.confidence import score_document
from apps.pilgrims.models import MedicalDocument, Pilgrim

TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="pilgrims_confidence_tests_")

STRUCTURED_DATA = {
    "diseases": ["Type 2 Diabetes"],
    "medications": [{"name": "Metformin", "dose": "500mg", "frequency": "twice daily"}],
    "allergies": [],
    "vaccinations": [],
}


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class ScoreDocumentTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        patcher = patch("apps.pilgrims.signals.run_pipeline")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pilgrim = Pilgrim.objects.create(full_name="Test Pilgrim", passport_number="P-CONF-1")

    def _make_document(self, filename, content_type, extracted_text="", extracted_json=None):
        return MedicalDocument.objects.create(
            pilgrim=self.pilgrim,
            file=SimpleUploadedFile(filename, b"fake content", content_type=content_type),
            extracted_text=extracted_text,
            extracted_json=extracted_json,
        )

    def test_pdf_with_extracted_data_scores_75_and_pending(self):
        document = self._make_document(
            "report.pdf", "application/pdf",
            extracted_text="Patient has Type 2 Diabetes...",
            extracted_json=STRUCTURED_DATA,
        )

        score, status = score_document(document)

        self.assertEqual(score, 75)
        self.assertEqual(status, "pending")
        document.refresh_from_db()
        self.assertEqual(document.confidence_score, 75)
        self.assertEqual(document.status, "pending")

    def test_image_with_extracted_data_scores_50_and_pending(self):
        document = self._make_document(
            "prescription.jpg", "image/jpeg",
            extracted_text="Metformin 500mg twice daily",
            extracted_json=STRUCTURED_DATA,
        )

        score, status = score_document(document)

        self.assertEqual(score, 50)
        self.assertEqual(status, "pending")

    def test_document_with_no_extracted_text_needs_review(self):
        document = self._make_document(
            "report.pdf", "application/pdf",
            extracted_text="",
            extracted_json=STRUCTURED_DATA,
        )

        score, status = score_document(document)

        self.assertEqual(score, 75)
        self.assertEqual(status, "needs_review")

    def test_document_with_no_extracted_json_needs_review(self):
        document = self._make_document(
            "prescription.jpg", "image/jpeg",
            extracted_text="Metformin 500mg twice daily",
            extracted_json=None,
        )

        score, status = score_document(document)

        self.assertEqual(score, 50)
        self.assertEqual(status, "needs_review")
