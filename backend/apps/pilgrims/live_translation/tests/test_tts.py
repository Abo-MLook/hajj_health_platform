import os
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from apps.pilgrims.live_translation.errors import SynthesisError
from apps.pilgrims.live_translation.tts import EspeakNgSpeechSynthesizer


CONFIG = {
    "ESPEAK_NG_EXECUTABLE": "espeak-ng",
    "ESPEAK_NG_SPEED_WPM": 165,
}


class TtsTests(SimpleTestCase):
    def test_uses_argument_list_returns_wav_and_deletes_tempfile(self):
        paths = []

        def runner(command, **kwargs):
            paths.append(command[command.index("-w") + 1])
            with open(paths[-1], "wb") as wav_file:
                wav_file.write(b"RIFFwav")
            self.assertIsInstance(command, list)
            self.assertNotIn("shell", kwargs)

        result = EspeakNgSpeechSynthesizer(CONFIG, runner).synthesize("hello", "en")
        self.assertEqual(result.wav_bytes, b"RIFFwav")
        self.assertFalse(os.path.exists(paths[0]))

    def test_subprocess_failure_becomes_synthesis_error(self):
        runner = MagicMock(side_effect=OSError("missing"))
        with self.assertRaises(SynthesisError):
            EspeakNgSpeechSynthesizer(CONFIG, runner).synthesize("hello", "en")
