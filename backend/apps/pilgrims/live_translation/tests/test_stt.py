from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.pilgrims.live_translation.errors import (
    SpeechRecognitionError,
    UnsupportedLanguageError,
)
from apps.pilgrims.live_translation.stt import FasterWhisperSpeechRecognizer
from apps.pilgrims.live_translation.tests.fakes import FakeWhisperModel


CONFIG = {
    "WHISPER_MODEL": "small",
    "WHISPER_DEVICE": "cpu",
    "WHISPER_COMPUTE_TYPE": "int8",
    "WHISPER_CPU_THREADS": 8,
    "WHISPER_BEAM_SIZE": 1,
    "WHISPER_MIN_SILENCE_DURATION_MS": 500,
}


class WhisperAdapterTests(SimpleTestCase):
    def test_auto_detection_and_explicit_lock(self):
        model = FakeWhisperModel(language="fa")
        recognizer = FasterWhisperSpeechRecognizer(CONFIG, model)
        transcript = recognizer.transcribe("unused.wav")
        self.assertEqual(transcript.language, "fa")
        self.assertEqual(transcript.language_probability, 0.8)
        recognizer.transcribe("unused.wav", "ur")
        self.assertEqual(model.kwargs["language"], "ur")
        self.assertTrue(model.kwargs["vad_filter"])
        self.assertFalse(model.kwargs["condition_on_previous_text"])

    def test_unsupported_and_empty_transcripts_fail(self):
        with self.assertRaises(UnsupportedLanguageError):
            FasterWhisperSpeechRecognizer(
                CONFIG, FakeWhisperModel(language="fr")
            ).transcribe("unused.wav")
        with self.assertRaises(SpeechRecognitionError):
            FasterWhisperSpeechRecognizer(
                CONFIG, FakeWhisperModel(text=" ")
            ).transcribe("unused.wav")

    @patch(
        "apps.pilgrims.live_translation.stt.whisper_setup_marker",
        return_value=Path("/definitely/missing/whisper.ready"),
    )
    def test_runtime_refuses_to_download_when_cache_marker_is_absent(self, marker):
        with self.assertRaisesMessage(
            SpeechRecognitionError, "live_translation_setup --download-whisper"
        ):
            FasterWhisperSpeechRecognizer(CONFIG).initialize()
