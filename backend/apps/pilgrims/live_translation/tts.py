import os
import subprocess
import tempfile

from django.conf import settings

from .domain import SynthesizedAudioChunk
from .errors import SynthesisError
from .validation import validate_language, validate_text


class EspeakNgSpeechSynthesizer:
    VOICES = {"ar": "ar", "fa": "fa", "ur": "ur", "en": "en-us"}

    def __init__(self, config=None, runner=None):
        self.config = config or settings.LOCAL_LIVE_TRANSLATION
        self.runner = runner or subprocess.run

    def synthesize(self, text, language):
        text = validate_text(text)
        language = validate_language(language)
        path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                path = tmp.name
            command = [
                self.config["ESPEAK_NG_EXECUTABLE"],
                "-v",
                self.VOICES[language],
                "-s",
                str(self.config["ESPEAK_NG_SPEED_WPM"]),
                "-w",
                path,
                text,
            ]
            self.runner(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            with open(path, "rb") as wav_file:
                wav_bytes = wav_file.read()
            if not wav_bytes:
                raise SynthesisError("espeak-ng produced an empty WAV file.")
            return SynthesizedAudioChunk(wav_bytes, language, text)
        except SynthesisError:
            raise
        except (OSError, subprocess.SubprocessError) as exc:
            raise SynthesisError(f"Local espeak-ng synthesis failed: {exc}") from exc
        finally:
            if path and os.path.exists(path):
                os.unlink(path)
