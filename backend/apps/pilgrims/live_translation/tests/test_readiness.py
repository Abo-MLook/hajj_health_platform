from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.pilgrims.live_translation.readiness import check_readiness
from apps.pilgrims.live_translation.validation import validate_ollama_url
from apps.pilgrims.live_translation.errors import ConfigurationError


CONFIG = {
    "TRANSLATOR_BACKEND": "ollama",
    "OLLAMA_URL": "http://127.0.0.1:11434",
    "OLLAMA_MODEL": "qwen3.5:9b",
    "OLLAMA_TIMEOUT_SECONDS": 60,
    "ALLOW_NON_LOOPBACK_OLLAMA": False,
    "WHISPER_MODEL": "small",
    "TTS_BACKEND": "espeak-ng",
    "TTS_ENABLED": True,
    "ESPEAK_NG_EXECUTABLE": "espeak-ng",
}


@override_settings(LOCAL_LIVE_TRANSLATION_ENABLED=True, LOCAL_LIVE_TRANSLATION=CONFIG)
class ReadinessTests(SimpleTestCase):
    @patch("apps.pilgrims.live_translation.readiness.whisper_setup_marker")
    @patch("apps.pilgrims.live_translation.readiness.shutil.which", return_value=None)
    @patch("apps.pilgrims.live_translation.readiness.importlib.util.find_spec")
    def test_reports_missing_python_tts_and_ollama(self, find_spec, which, marker):
        find_spec.return_value = None
        marker.return_value = Path("/missing")
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            report = check_readiness()
        commands = {issue.command for issue in report.issues}
        self.assertIn(
            "python -m pip install -r requirements-live-translation.txt", commands
        )
        self.assertIn("sudo pacman -S --needed ollama espeak-ng", commands)
        self.assertIn("ollama serve", commands)

    @patch("apps.pilgrims.live_translation.readiness.whisper_setup_marker")
    @patch("apps.pilgrims.live_translation.readiness.shutil.which", return_value="/bin/espeak-ng")
    @patch("apps.pilgrims.live_translation.readiness.importlib.util.find_spec", return_value=MagicMock())
    def test_reports_missing_model(self, find_spec, which, marker):
        marker.return_value.exists.return_value = True
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"models":[]}'
        with patch("urllib.request.urlopen", return_value=response):
            report = check_readiness()
        self.assertIn(
            "ollama pull qwen3.5:9b",
            {issue.command for issue in report.issues},
        )

    def test_non_loopback_rejected_without_opt_in(self):
        with self.assertRaises(ConfigurationError):
            validate_ollama_url("http://192.168.1.5:11434")
        self.assertEqual(
            validate_ollama_url("http://192.168.1.5:11434", True),
            "http://192.168.1.5:11434",
        )
