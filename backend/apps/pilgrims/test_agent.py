from unittest.mock import MagicMock, patch

from django.test import TestCase

from .agent import review_agent
from .models import MedicalDocument, Pilgrim

_DIRTY_JSON = {
    "diseases": ["Diabetis"],
    "medications": [{"name": "Metfomin", "dose": "50mg", "frequency": "daily"}],
    "allergies": [],
    "vaccinations": [],
}


def _make_document(confidence=50, extracted_text="Patient has Diabetis and takes Metfomin 50mg daily.", extracted_json=None):
    pilgrim = Pilgrim.objects.create(full_name="Test Patient", passport_number=f"TEST-{id(object())}")
    # Patch the signal handler so the real pipeline does not fire during setup
    # and overwrite extracted_json with AI-corrected values before the test runs.
    with patch("apps.pilgrims.signals.run_pipeline"):
        doc = MedicalDocument.objects.create(
            pilgrim=pilgrim,
            original_filename="test.jpg",
            file_type="jpg",
            confidence_score=confidence,
            status="pending",
            extracted_text=extracted_text,
            extracted_json=extracted_json if extracted_json is not None else dict(_DIRTY_JSON),
        )
    return doc


CORRECTED_RESPONSE = '''{
  "diseases": ["Diabetes"],
  "medications": [{"name": "Metformin", "dose": "500mg", "frequency": "daily"}],
  "allergies": [],
  "vaccinations": [],
  "corrections_made": ["Diabetis corrected to Diabetes", "Metfomin corrected to Metformin", "50mg corrected to 500mg"]
}'''

EMPTY_RESPONSE = '''{
  "diseases": [],
  "medications": [],
  "allergies": [],
  "vaccinations": [],
  "corrections_made": []
}'''


class ReviewAgentSkipTest(TestCase):
    def test_skips_when_confidence_75_or_above(self):
        doc = _make_document(confidence=75)
        result = review_agent(doc)
        self.assertTrue(result["skipped"])
        self.assertEqual(result["attempts"], 0)

    def test_skips_when_confidence_above_75(self):
        doc = _make_document(confidence=100)
        result = review_agent(doc)
        self.assertTrue(result["skipped"])


class ReviewAgentSuccessTest(TestCase):
    @patch("apps.pilgrims.agent._get_client")
    def test_approves_and_updates_json_on_success(self, mock_get_client):
        mock_choice = MagicMock()
        mock_choice.message.content = CORRECTED_RESPONSE
        mock_get_client.return_value.chat.completions.create.return_value.choices = [mock_choice]

        doc = _make_document(confidence=50)
        result = review_agent(doc)

        doc.refresh_from_db()
        self.assertEqual(result["final_status"], "approved")
        self.assertEqual(doc.status, "approved")
        self.assertEqual(doc.extracted_json["diseases"], ["Diabetes"])
        self.assertEqual(doc.extracted_json["medications"][0]["name"], "Metformin")
        self.assertEqual(doc.extracted_json["medications"][0]["dose"], "500mg")

    @patch("apps.pilgrims.agent._get_client")
    def test_improved_true_when_corrections_differ(self, mock_get_client):
        mock_choice = MagicMock()
        mock_choice.message.content = CORRECTED_RESPONSE
        mock_get_client.return_value.chat.completions.create.return_value.choices = [mock_choice]

        doc = _make_document(confidence=50)
        result = review_agent(doc)

        self.assertTrue(result["improved"])
        self.assertIn("Diabetis corrected to Diabetes", result["corrections_made"])

    @patch("apps.pilgrims.agent._get_client")
    def test_improved_false_when_no_changes(self, mock_get_client):
        same_data = {
            "diseases": ["Diabetes"],
            "medications": [{"name": "Metformin", "dose": "500mg", "frequency": "daily"}],
            "allergies": [],
            "vaccinations": [],
        }
        response_json = dict(same_data, corrections_made=[])
        mock_choice = MagicMock()
        mock_choice.message.content = str(response_json).replace("'", '"')
        mock_get_client.return_value.chat.completions.create.return_value.choices = [mock_choice]

        doc = _make_document(confidence=50, extracted_json=same_data)
        result = review_agent(doc)

        self.assertFalse(result["improved"])
        self.assertEqual(result["final_status"], "approved")

    @patch("apps.pilgrims.agent._get_client")
    def test_preserves_identity_fields_from_original_extraction(self, mock_get_client):
        """The review response has no patient_name/demographics — they must
        survive from the original extraction instead of being erased."""
        mock_choice = MagicMock()
        mock_choice.message.content = CORRECTED_RESPONSE
        mock_get_client.return_value.chat.completions.create.return_value.choices = [mock_choice]

        original = dict(
            _DIRTY_JSON,
            patient_name="Fatima Al-Zahrani",
            date_of_birth="1980-05-20",
            gender="female",
            nationality="Saudi",
        )
        doc = _make_document(confidence=50, extracted_json=original)
        review_agent(doc)

        doc.refresh_from_db()
        self.assertEqual(doc.extracted_json["patient_name"], "Fatima Al-Zahrani")
        self.assertEqual(doc.extracted_json["date_of_birth"], "1980-05-20")
        self.assertEqual(doc.extracted_json["gender"], "female")
        self.assertEqual(doc.extracted_json["nationality"], "Saudi")
        # corrections still applied
        self.assertEqual(doc.extracted_json["diseases"], ["Diabetes"])

    @patch("apps.pilgrims.agent._get_client")
    def test_review_response_identity_fields_win_when_present(self, mock_get_client):
        """If the review response itself contains identity fields, use them."""
        response = CORRECTED_RESPONSE.replace(
            '"diseases"',
            '"patient_name": "Corrected Name", "diseases"',
        )
        mock_choice = MagicMock()
        mock_choice.message.content = response
        mock_get_client.return_value.chat.completions.create.return_value.choices = [mock_choice]

        doc = _make_document(confidence=50, extracted_json=dict(_DIRTY_JSON, patient_name="Old Name"))
        review_agent(doc)

        doc.refresh_from_db()
        self.assertEqual(doc.extracted_json["patient_name"], "Corrected Name")

    @patch("apps.pilgrims.agent._get_client")
    def test_succeeds_on_second_attempt(self, mock_get_client):
        mock_choice = MagicMock()
        mock_choice.message.content = CORRECTED_RESPONSE
        mock_api = mock_get_client.return_value.chat.completions.create
        # first call raises, second succeeds
        mock_api.side_effect = [Exception("timeout"), MagicMock(choices=[mock_choice])]

        doc = _make_document(confidence=50)
        result = review_agent(doc)

        self.assertEqual(result["final_status"], "approved")
        self.assertEqual(result["attempts"], 2)


class ReviewAgentFailureTest(TestCase):
    @patch("apps.pilgrims.agent._get_client")
    def test_needs_review_after_3_failed_attempts(self, mock_get_client):
        mock_get_client.return_value.chat.completions.create.side_effect = Exception("API error")

        doc = _make_document(confidence=50)
        result = review_agent(doc)

        doc.refresh_from_db()
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(doc.status, "needs_review")
        self.assertEqual(result["attempts"], 3)
        self.assertFalse(result["improved"])

    @patch("apps.pilgrims.agent._get_client")
    def test_needs_review_when_all_attempts_return_empty(self, mock_get_client):
        mock_choice = MagicMock()
        mock_choice.message.content = EMPTY_RESPONSE
        mock_get_client.return_value.chat.completions.create.return_value.choices = [mock_choice]

        doc = _make_document(confidence=50)
        result = review_agent(doc)

        doc.refresh_from_db()
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(doc.status, "needs_review")

    def test_needs_review_when_no_extracted_text(self):
        doc = _make_document(confidence=50, extracted_text="")
        result = review_agent(doc)

        doc.refresh_from_db()
        self.assertEqual(result["final_status"], "needs_review")
        self.assertFalse(result["improved"])
