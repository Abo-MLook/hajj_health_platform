from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class SetupCommandTests(SimpleTestCase):
    @patch(
        "apps.pilgrims.live_translation.management.commands.live_translation_setup.check_readiness"
    )
    def test_check_does_not_download(self, readiness):
        readiness.return_value.to_dict.return_value = {"ready": False}
        output = StringIO()
        with patch(
            "apps.pilgrims.live_translation.management.commands.live_translation_setup."
            "FasterWhisperSpeechRecognizer"
        ) as recognizer:
            call_command("live_translation_setup", "--check", stdout=output)
        recognizer.assert_not_called()

    @patch(
        "apps.pilgrims.live_translation.management.commands.live_translation_setup."
        "FasterWhisperSpeechRecognizer"
    )
    def test_download_whisper_is_explicit(self, recognizer):
        call_command("live_translation_setup", "--download-whisper", stdout=StringIO())
        recognizer.return_value.download_model.assert_called_once()

    @patch(
        "apps.pilgrims.live_translation.management.commands.live_translation_setup."
        "Command._ollama_request"
    )
    def test_verify_and_warm_ollama(self, request):
        request.return_value = {"models": [{"name": "qwen3.5:9b"}]}
        call_command("live_translation_setup", "--verify-ollama", stdout=StringIO())
        request.assert_called_with("/api/tags", timeout=5)
        request.reset_mock()
        call_command("live_translation_setup", "--warm-ollama", stdout=StringIO())
        payload = request.call_args.args[1]
        self.assertEqual(payload["prompt"], "Reply OK.")
        self.assertEqual(payload["keep_alive"], -1)
        self.assertNotIn("user", payload)

    @patch(
        "apps.pilgrims.live_translation.management.commands.live_translation_setup."
        "Command._warm_ollama"
    )
    @patch(
        "apps.pilgrims.live_translation.management.commands.live_translation_setup."
        "Command._verify_ollama"
    )
    @patch(
        "apps.pilgrims.live_translation.management.commands.live_translation_setup."
        "Command._download_whisper"
    )
    @patch(
        "apps.pilgrims.live_translation.management.commands.live_translation_setup."
        "Command._check"
    )
    def test_all_combines_explicit_operations(self, check, download, verify, warm):
        call_command("live_translation_setup", "--all", stdout=StringIO())
        check.assert_called_once()
        download.assert_called_once()
        verify.assert_called_once()
        warm.assert_called_once()
