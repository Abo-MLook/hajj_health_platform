import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.pilgrims.merging import merge_health_profile
from apps.pilgrims.models import HealthProfile, MedicalDocument, Pilgrim

TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="pilgrims_merge_tests_")


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class MergeHealthProfileTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        patcher = patch("apps.pilgrims.signals.run_pipeline")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pilgrim = Pilgrim.objects.create(full_name="Test Pilgrim", passport_number="P-MERGE-1")

    def _make_document(self, filename, extracted_json, status="pending", confidence_score=75):
        return MedicalDocument.objects.create(
            pilgrim=self.pilgrim,
            file=SimpleUploadedFile(filename, b"fake content", content_type="application/pdf"),
            extracted_text="placeholder text",
            extracted_json=extracted_json,
            status=status,
            confidence_score=confidence_score,
        )

    def test_merges_and_dedupes_data_from_multiple_documents(self):
        self._make_document("doc1.pdf", {
            "diseases": ["Type 2 Diabetes"],
            "medications": [{"name": "Metformin", "dose": "500mg", "frequency": "twice daily"}],
            "allergies": ["Penicillin"],
            "vaccinations": ["COVID-19"],
        }, confidence_score=75)
        self._make_document("doc2.pdf", {
            "diseases": ["Type 2 Diabetes", "Hypertension"],
            "medications": [{"name": "Metformin", "dose": "500mg", "frequency": "twice daily"}],
            "allergies": ["Penicillin", "Sulfa drugs"],
            "vaccinations": ["Influenza"],
        }, confidence_score=50)

        profile = merge_health_profile(self.pilgrim)

        self.assertEqual(profile.diseases_text, "Hypertension, Type 2 Diabetes")
        self.assertEqual(profile.allergies_text, "Penicillin, Sulfa drugs")
        self.assertEqual(profile.vaccinations_text, "COVID-19, Influenza")
        self.assertEqual(profile.medications_text, "Metformin (500mg twice daily)")
        self.assertEqual(profile.status, "pending")
        self.assertEqual(profile.confidence_score, 62)

    def test_conflicting_medication_details_mark_profile_needs_review(self):
        self._make_document("doc1.pdf", {
            "diseases": [], "allergies": [], "vaccinations": [],
            "medications": [{"name": "Metformin", "dose": "500mg", "frequency": "twice daily"}],
        })
        self._make_document("doc2.pdf", {
            "diseases": [], "allergies": [], "vaccinations": [],
            "medications": [{"name": "Metformin", "dose": "850mg", "frequency": "once daily"}],
        })

        profile = merge_health_profile(self.pilgrim)

        self.assertEqual(profile.status, "needs_review")
        self.assertEqual(profile.confidence_score, 0)

    def test_rejected_and_empty_documents_are_ignored(self):
        self._make_document("doc1.pdf", {
            "diseases": ["Asthma"], "medications": [], "allergies": [], "vaccinations": [],
        }, status="rejected")
        self._make_document("doc2.pdf", None)

        profile = merge_health_profile(self.pilgrim)

        self.assertEqual(profile.diseases_text, "")
        self.assertEqual(profile.status, "pending")
        self.assertEqual(profile.confidence_score, 0)

    def test_creates_profile_when_none_exists(self):
        self.assertFalse(HealthProfile.objects.filter(pilgrim=self.pilgrim).exists())

        profile = merge_health_profile(self.pilgrim)

        self.assertTrue(HealthProfile.objects.filter(pilgrim=self.pilgrim).exists())
        self.assertEqual(profile.pilgrim, self.pilgrim)

    def test_updates_existing_profile(self):
        existing = HealthProfile.objects.create(pilgrim=self.pilgrim, diseases_text="Old data")
        self._make_document("doc1.pdf", {
            "diseases": ["Asthma"], "medications": [], "allergies": [], "vaccinations": [],
        })

        profile = merge_health_profile(self.pilgrim)

        self.assertEqual(profile.pk, existing.pk)
        self.assertEqual(profile.diseases_text, "Asthma")
