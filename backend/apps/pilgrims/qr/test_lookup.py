from django.test import TestCase

from apps.pilgrims.models import HealthProfile, Pilgrim
from apps.pilgrims.qr.lookup import get_health_profile_by_patient_id, get_pilgrim_by_patient_id


class LookupByPatientIdTests(TestCase):
    def setUp(self):
        self.pilgrim = Pilgrim.objects.create(full_name="Test Pilgrim", passport_number="P-LOOKUP-1")

    def test_get_pilgrim_by_patient_id_returns_matching_pilgrim(self):
        result = get_pilgrim_by_patient_id(self.pilgrim.patient_id)

        self.assertEqual(result, self.pilgrim)

    def test_get_pilgrim_by_patient_id_returns_none_for_unknown_id(self):
        result = get_pilgrim_by_patient_id("UNKNOWN000000")

        self.assertIsNone(result)

    def test_get_pilgrim_by_patient_id_returns_none_for_empty_id(self):
        self.assertIsNone(get_pilgrim_by_patient_id(""))
        self.assertIsNone(get_pilgrim_by_patient_id(None))

    def test_get_health_profile_by_patient_id_returns_profile_when_present(self):
        profile = HealthProfile.objects.create(pilgrim=self.pilgrim, diseases_text="None reported")

        result = get_health_profile_by_patient_id(self.pilgrim.patient_id)

        self.assertEqual(result, profile)

    def test_get_health_profile_by_patient_id_returns_none_when_profile_missing(self):
        result = get_health_profile_by_patient_id(self.pilgrim.patient_id)

        self.assertIsNone(result)

    def test_get_health_profile_by_patient_id_returns_none_for_unknown_id(self):
        result = get_health_profile_by_patient_id("UNKNOWN000000")

        self.assertIsNone(result)
