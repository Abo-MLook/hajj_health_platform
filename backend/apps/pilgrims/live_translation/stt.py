import os
from pathlib import Path

from django.conf import settings

from .domain import Transcript
from .errors import SpeechRecognitionError
from .validation import validate_language


def whisper_setup_marker(model_name):
    safe_name = model_name.replace("/", "_")
    root = Path(
        os.environ.get(
            "LOCAL_LIVE_TRANSLATION_CACHE",
            Path.home() / ".cache" / "hajj_health_platform" / "live_translation",
        )
    )
    return root / f"whisper-{safe_name}.ready"


class FasterWhisperSpeechRecognizer:
    def __init__(self, config=None, model=None, require_setup_marker=True):
        self.config = config or settings.LOCAL_LIVE_TRANSLATION
        self._model = model
        self.require_setup_marker = require_setup_marker

    def initialize(self):
        if self._model is not None:
            return self._model
        marker = whisper_setup_marker(self.config["WHISPER_MODEL"])
        if self.require_setup_marker and not marker.exists():
            raise SpeechRecognitionError(
                "Whisper model is not cached for runtime use. Run: "
                "python manage.py live_translation_setup --download-whisper"
            )
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise SpeechRecognitionError(
                "faster-whisper is missing. Run: python -m pip install -r "
                "requirements-live-translation.txt"
            ) from exc
        try:
            self._model = WhisperModel(
                self.config["WHISPER_MODEL"],
                device=self.config["WHISPER_DEVICE"],
                compute_type=self.config["WHISPER_COMPUTE_TYPE"],
                cpu_threads=self.config["WHISPER_CPU_THREADS"],
                local_files_only=self.require_setup_marker,
            )
        except Exception as exc:
            raise SpeechRecognitionError(
                "Unable to initialize cached Whisper model. Run: "
                "python manage.py live_translation_setup --download-whisper"
            ) from exc
        return self._model

    def download_model(self):
        model = self.initialize()
        marker = whisper_setup_marker(self.config["WHISPER_MODEL"])
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("cached\n", encoding="ascii")
        return model

    def transcribe(self, audio_path, language=None):
        locked_language = validate_language(language) if language else None
        model = self.initialize()
        try:
            segments, info = model.transcribe(
                audio_path,
                language=locked_language,
                beam_size=self.config["WHISPER_BEAM_SIZE"],
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": self.config[
                        "WHISPER_MIN_SILENCE_DURATION_MS"
                    ]
                },
                condition_on_previous_text=False,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
        except Exception as exc:
            raise SpeechRecognitionError(f"Speech recognition failed: {exc}") from exc
        if not text:
            raise SpeechRecognitionError("Speech recognition returned empty text.")
        detected_language = locked_language or getattr(info, "language", None)
        detected_language = validate_language(detected_language)
        probability = getattr(info, "language_probability", None)
        return Transcript(text, detected_language, probability)
