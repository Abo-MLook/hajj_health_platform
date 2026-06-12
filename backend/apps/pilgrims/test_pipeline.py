import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.pilgrims.models import MedicalDocument, Pilgrim
from apps.pilgrims.pipeline import run_pipeline

TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="pilgrims_pipeline_tests_")

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
class RunPipelineTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        patcher = patch("apps.pilgrims.signals.run_pipeline")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pilgrim = Pilgrim.objects.create(
            full_name="Test Pilgrim",
            passport_number="P-PIPELINE-1",
        )
        self.document = MedicalDocument.objects.create(
            pilgrim=self.pilgrim,
            file=SimpleUploadedFile("report.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
            original_filename="report.pdf",
            file_type="pdf",
        )

    @patch("apps.pilgrims.pipeline.merge_health_profile")
    @patch("apps.pilgrims.pipeline.score_document")
    @patch("apps.pilgrims.pipeline.extract_json_from_document")
    @patch("apps.pilgrims.pipeline.extract_text_from_document")
    def test_pipeline_calls_all_steps_in_order(
        self, mock_extract_text, mock_extract_json, mock_score, mock_merge
    ):
        mock_merge.return_value.status = "pending"

        run_pipeline(self.document)

        mock_extract_text.assert_called_once_with(self.document)
        mock_extract_json.assert_called_once_with(self.document)
        mock_score.assert_called_once_with(self.document)
        mock_merge.assert_called_once_with(self.document.pilgrim)

    @patch("apps.pilgrims.pipeline.merge_health_profile")
    @patch("apps.pilgrims.pipeline.score_document")
    @patch("apps.pilgrims.pipeline.extract_json_from_document")
    @patch("apps.pilgrims.pipeline.extract_text_from_document")
    def test_pipeline_returns_correct_summary(
        self, mock_extract_text, mock_extract_json, mock_score, mock_merge
    ):
        mock_merge.return_value.status = "pending"

        # Simulate each step writing its results to the document
        def fake_extract_text(doc):
            doc.extracted_text = "Patient has Type 2 Diabetes..."
            doc.save(update_fields=["extracted_text", "updated_at"])

        def fake_extract_json(doc):
            doc.extracted_json = STRUCTURED_DATA
            doc.save(update_fields=["extracted_json", "updated_at"])

        def fake_score(doc):
            doc.confidence_score = 75
            doc.status = "pending"
            doc.save(update_fields=["confidence_score", "status", "updated_at"])

        mock_extract_text.side_effect = fake_extract_text
        mock_extract_json.side_effect = fake_extract_json
        mock_score.side_effect = fake_score

        summary = run_pipeline(self.document)

        self.assertEqual(summary["extracted_text_length"], len("Patient has Type 2 Diabetes..."))
        self.assertEqual(summary["extracted_json"], STRUCTURED_DATA)
        self.assertEqual(summary["confidence_score"], 75)
        self.assertEqual(summary["status"], "pending")
        self.assertEqual(summary["health_profile_status"], "pending")

    @patch("apps.pilgrims.pipeline.merge_health_profile")
    @patch("apps.pilgrims.pipeline.score_document")
    @patch("apps.pilgrims.pipeline.extract_json_from_document")
    @patch("apps.pilgrims.pipeline.extract_text_from_document")
    def test_signal_does_not_retrigger_pipeline_on_update(
        self, mock_extract_text, mock_extract_json, mock_score, mock_merge
    ):
        """Saving an existing document (e.g. changing status) must not re-run the pipeline."""
        mock_merge.return_value.status = "pending"

        # Simulate an admin update — not a new upload
        self.document.status = "approved"
        self.document.save(update_fields=["status"])

        mock_extract_text.assert_not_called()
        mock_extract_json.assert_not_called()
        mock_score.assert_not_called()
        mock_merge.assert_not_called()

    @patch("apps.pilgrims.pipeline.review_agent")
    @patch("apps.pilgrims.pipeline.merge_health_profile")
    @patch("apps.pilgrims.pipeline.score_document")
    @patch("apps.pilgrims.pipeline.extract_json_from_document")
    @patch("apps.pilgrims.pipeline.extract_text_from_document")
    def test_review_agent_called_for_image_document(
        self, mock_extract_text, mock_extract_json, mock_score, mock_merge, mock_agent
    ):
        """Pipeline calls review_agent when confidence_score is below 75 (image)."""
        mock_merge.return_value.status = "pending"

        def fake_score(doc):
            doc.confidence_score = 50
            doc.save(update_fields=["confidence_score", "updated_at"])

        mock_score.side_effect = fake_score

        run_pipeline(self.document)

        mock_agent.assert_called_once_with(self.document)

    @patch("apps.pilgrims.pipeline.review_agent")
    @patch("apps.pilgrims.pipeline.merge_health_profile")
    @patch("apps.pilgrims.pipeline.score_document")
    @patch("apps.pilgrims.pipeline.extract_json_from_document")
    @patch("apps.pilgrims.pipeline.extract_text_from_document")
    def test_review_agent_not_called_for_pdf_document(
        self, mock_extract_text, mock_extract_json, mock_score, mock_merge, mock_agent
    ):
        """Pipeline skips review_agent when confidence_score is 75 or above (PDF)."""
        mock_merge.return_value.status = "pending"

        def fake_score(doc):
            doc.confidence_score = 75
            doc.save(update_fields=["confidence_score", "updated_at"])

        mock_score.side_effect = fake_score

        run_pipeline(self.document)

        mock_agent.assert_not_called()

    @patch("apps.pilgrims.pipeline.review_agent")
    @patch("apps.pilgrims.pipeline.merge_health_profile")
    @patch("apps.pilgrims.pipeline.score_document")
    @patch("apps.pilgrims.pipeline.extract_json_from_document")
    @patch("apps.pilgrims.pipeline.extract_text_from_document")
    def test_merge_always_runs_after_agent(
        self, mock_extract_text, mock_extract_json, mock_score, mock_merge, mock_agent
    ):
        """merge_health_profile runs regardless of whether review_agent was called."""
        mock_merge.return_value.status = "pending"

        def fake_score(doc):
            doc.confidence_score = 50
            doc.save(update_fields=["confidence_score", "updated_at"])

        mock_score.side_effect = fake_score

        run_pipeline(self.document)

        mock_agent.assert_called_once()
        mock_merge.assert_called_once_with(self.document.pilgrim)

    @patch("apps.pilgrims.pipeline.apply_demographics")
    @patch("apps.pilgrims.pipeline.merge_health_profile")
    @patch("apps.pilgrims.pipeline.score_document")
    @patch("apps.pilgrims.pipeline.extract_json_from_document")
    @patch("apps.pilgrims.pipeline.extract_text_from_document")
    def test_demographics_applied_for_every_document(
        self, mock_extract_text, mock_extract_json, mock_score, mock_merge, mock_demographics
    ):
        """apply_demographics runs in the pipeline regardless of confidence."""
        mock_merge.return_value.status = "pending"

        def fake_score(doc):
            doc.confidence_score = 75
            doc.save(update_fields=["confidence_score", "updated_at"])

        mock_score.side_effect = fake_score

        run_pipeline(self.document)

        mock_demographics.assert_called_once_with(self.document)
