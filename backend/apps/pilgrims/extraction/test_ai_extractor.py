from unittest import TestCase
from unittest.mock import MagicMock, patch

from apps.pilgrims.extraction.ai_extractor import extract_structured_data

EXPECTED_DATA = {
    "diseases": ["Type 2 Diabetes"],
    "medications": [{"name": "Metformin", "dose": "500mg", "frequency": "twice daily"}],
    "allergies": ["Penicillin"],
    "vaccinations": ["COVID-19"],
}


@patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key"})
class ExtractStructuredDataTests(TestCase):
    @patch("apps.pilgrims.extraction.ai_extractor.genai.GenerativeModel")
    @patch("apps.pilgrims.extraction.ai_extractor.genai.configure")
    def test_parses_clean_json_response(self, mock_configure, mock_model_cls):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(text='{"diseases": ["Type 2 Diabetes"], '
                                                                    '"medications": [{"name": "Metformin", '
                                                                    '"dose": "500mg", "frequency": "twice daily"}], '
                                                                    '"allergies": ["Penicillin"], '
                                                                    '"vaccinations": ["COVID-19"]}')
        mock_model_cls.return_value = mock_model

        result = extract_structured_data("Patient has Type 2 Diabetes...")

        self.assertEqual(result, EXPECTED_DATA)

    @patch("apps.pilgrims.extraction.ai_extractor.genai.GenerativeModel")
    @patch("apps.pilgrims.extraction.ai_extractor.genai.configure")
    def test_unwraps_markdown_fenced_json(self, mock_configure, mock_model_cls):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(
            text='```json\n{"diseases": [], "medications": [], "allergies": [], "vaccinations": []}\n```'
        )
        mock_model_cls.return_value = mock_model

        result = extract_structured_data("Some document text")

        self.assertEqual(result, {"diseases": [], "medications": [], "allergies": [], "vaccinations": []})

    @patch("apps.pilgrims.extraction.ai_extractor.genai.GenerativeModel")
    @patch("apps.pilgrims.extraction.ai_extractor.genai.configure")
    def test_returns_none_for_malformed_json(self, mock_configure, mock_model_cls):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(text="not valid json at all")
        mock_model_cls.return_value = mock_model

        result = extract_structured_data("Some document text")

        self.assertIsNone(result)

    @patch("apps.pilgrims.extraction.ai_extractor.genai.GenerativeModel")
    @patch("apps.pilgrims.extraction.ai_extractor.genai.configure")
    def test_returns_none_when_api_call_fails(self, mock_configure, mock_model_cls):
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API error")
        mock_model_cls.return_value = mock_model

        result = extract_structured_data("Some document text")

        self.assertIsNone(result)

    def test_returns_none_for_empty_text_without_calling_api(self):
        result = extract_structured_data("   ")

        self.assertIsNone(result)
