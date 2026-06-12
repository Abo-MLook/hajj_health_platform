from unittest import TestCase
from unittest.mock import MagicMock, patch

from apps.pilgrims.extraction.ai_extractor import extract_structured_data

CLEAN_JSON = (
    '{"patient_name": "Fatima Al-Zahrani", '
    '"date_of_birth": "1980-05-20", '
    '"gender": "female", '
    '"nationality": "Saudi", '
    '"diseases": ["Type 2 Diabetes"], '
    '"medications": [{"name": "Metformin", "dose": "500mg", "frequency": "twice daily"}], '
    '"allergies": ["Penicillin"], '
    '"vaccinations": ["COVID-19"]}'
)

FENCED_JSON = (
    "```json\n"
    '{"patient_name": null, "diseases": [], "medications": [], "allergies": [], "vaccinations": []}'
    "\n```"
)


def _mock_client(content):
    mock_choice = MagicMock()
    mock_choice.message.content = content
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [mock_choice]
    return client


@patch.dict("os.environ", {"GROQ_API_KEY": "fake-key"})
class ExtractStructuredDataTests(TestCase):

    @patch("apps.pilgrims.extraction.ai_extractor._get_client")
    def test_parses_clean_json_response(self, mock_get_client):
        mock_get_client.return_value = _mock_client(CLEAN_JSON)

        result = extract_structured_data("Patient has Type 2 Diabetes...")

        self.assertEqual(result["diseases"], ["Type 2 Diabetes"])
        self.assertEqual(result["medications"][0]["name"], "Metformin")
        self.assertEqual(result["medications"][0]["dose"], "500mg")
        self.assertEqual(result["allergies"], ["Penicillin"])
        self.assertEqual(result["vaccinations"], ["COVID-19"])
        self.assertEqual(result["patient_name"], "Fatima Al-Zahrani")
        self.assertEqual(result["date_of_birth"], "1980-05-20")
        self.assertEqual(result["gender"], "female")
        self.assertEqual(result["nationality"], "Saudi")

    @patch("apps.pilgrims.extraction.ai_extractor._get_client")
    def test_unwraps_markdown_fenced_json(self, mock_get_client):
        mock_get_client.return_value = _mock_client(FENCED_JSON)

        result = extract_structured_data("Some document text")

        self.assertEqual(result["diseases"], [])
        self.assertEqual(result["medications"], [])
        self.assertIsNone(result["patient_name"])

    @patch("apps.pilgrims.extraction.ai_extractor._get_client")
    def test_returns_none_for_malformed_json(self, mock_get_client):
        mock_get_client.return_value = _mock_client("not valid json at all")

        result = extract_structured_data("Some document text")

        self.assertIsNone(result)

    @patch("apps.pilgrims.extraction.ai_extractor._get_client")
    def test_returns_none_when_api_call_fails(self, mock_get_client):
        mock_get_client.return_value.chat.completions.create.side_effect = Exception("API error")

        result = extract_structured_data("Some document text")

        self.assertIsNone(result)

    def test_returns_none_for_empty_text_without_calling_api(self):
        result = extract_structured_data("   ")
        self.assertIsNone(result)

    def test_returns_none_for_none_text(self):
        result = extract_structured_data(None)
        self.assertIsNone(result)

    @patch("apps.pilgrims.extraction.ai_extractor._get_client")
    def test_api_called_with_text_in_prompt(self, mock_get_client):
        mock_get_client.return_value = _mock_client(CLEAN_JSON)
        sample_text = "Patient has Hypertension"

        extract_structured_data(sample_text)

        call_args = mock_get_client.return_value.chat.completions.create.call_args
        prompt_content = call_args[1]["messages"][0]["content"]
        self.assertIn(sample_text, prompt_content)
