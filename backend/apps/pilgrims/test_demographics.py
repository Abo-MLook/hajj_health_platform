from datetime import date
from unittest.mock import patch

from django.test import TestCase

from .demographics import _parse_iso_date, apply_demographics
from .models import MedicalDocument, Pilgrim

FULL_JSON = {
    "patient_name": "Abdullah Al-Rashidi",
    "date_of_birth": "1965-03-12",
    "gender": "male",
    "nationality": "Saudi",
    "diseases": ["Type 2 Diabetes"],
    "medications": [],
    "allergies": [],
    "vaccinations": [],
}


def _make_document(pilgrim, extracted_json):
    with patch("apps.pilgrims.signals.run_pipeline"):
        return MedicalDocument.objects.create(
            pilgrim=pilgrim,
            original_filename="test.pdf",
            file_type="pdf",
            extracted_json=extracted_json,
        )


class ParseIsoDateTests(TestCase):
    def test_parses_valid_date(self):
        self.assertEqual(_parse_iso_date("1965-03-12"), date(1965, 3, 12))

    def test_rejects_invalid_format(self):
        self.assertIsNone(_parse_iso_date("12/03/1965"))
        self.assertIsNone(_parse_iso_date("not a date"))

    def test_rejects_none_and_non_strings(self):
        self.assertIsNone(_parse_iso_date(None))
        self.assertIsNone(_parse_iso_date(1965))

    def test_rejects_future_date(self):
        self.assertIsNone(_parse_iso_date("2099-01-01"))

    def test_rejects_implausibly_old_date(self):
        self.assertIsNone(_parse_iso_date("1850-01-01"))


class ApplyDemographicsTests(TestCase):
    def setUp(self):
        self.pilgrim = Pilgrim.objects.create(
            full_name="Test Pilgrim", passport_number="P-DEMO-1"
        )

    def test_fills_all_blank_fields(self):
        document = _make_document(self.pilgrim, FULL_JSON)

        updated = apply_demographics(document)

        self.pilgrim.refresh_from_db()
        self.assertEqual(self.pilgrim.date_of_birth, date(1965, 3, 12))
        self.assertEqual(self.pilgrim.gender, "male")
        self.assertEqual(self.pilgrim.nationality, "Saudi")
        self.assertEqual(set(updated), {"date_of_birth", "gender", "nationality"})

    def test_never_overwrites_existing_values(self):
        self.pilgrim.date_of_birth = date(1970, 1, 1)
        self.pilgrim.gender = "female"
        self.pilgrim.nationality = "Egyptian"
        self.pilgrim.save()
        document = _make_document(self.pilgrim, FULL_JSON)

        updated = apply_demographics(document)

        self.pilgrim.refresh_from_db()
        self.assertEqual(self.pilgrim.date_of_birth, date(1970, 1, 1))
        self.assertEqual(self.pilgrim.gender, "female")
        self.assertEqual(self.pilgrim.nationality, "Egyptian")
        self.assertEqual(updated, [])

    def test_ignores_invalid_gender(self):
        data = dict(FULL_JSON, gender="unknown")
        document = _make_document(self.pilgrim, data)

        apply_demographics(document)

        self.pilgrim.refresh_from_db()
        self.assertEqual(self.pilgrim.gender, "")

    def test_normalizes_gender_case(self):
        data = dict(FULL_JSON, gender="Male")
        document = _make_document(self.pilgrim, data)

        apply_demographics(document)

        self.pilgrim.refresh_from_db()
        self.assertEqual(self.pilgrim.gender, "male")

    def test_ignores_invalid_date(self):
        data = dict(FULL_JSON, date_of_birth="03/12/1965")
        document = _make_document(self.pilgrim, data)

        apply_demographics(document)

        self.pilgrim.refresh_from_db()
        self.assertIsNone(self.pilgrim.date_of_birth)

    def test_handles_missing_extracted_json(self):
        document = _make_document(self.pilgrim, None)

        updated = apply_demographics(document)

        self.assertEqual(updated, [])

    def test_handles_null_demographic_fields(self):
        data = dict(FULL_JSON, date_of_birth=None, gender=None, nationality=None)
        document = _make_document(self.pilgrim, data)

        updated = apply_demographics(document)

        self.assertEqual(updated, [])

    def test_age_property_computed_from_dob(self):
        document = _make_document(self.pilgrim, FULL_JSON)
        apply_demographics(document)
        self.pilgrim.refresh_from_db()

        today = date.today()
        born = date(1965, 3, 12)
        expected = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        self.assertEqual(self.pilgrim.age, expected)

    def test_age_is_none_without_dob(self):
        self.assertIsNone(self.pilgrim.age)
