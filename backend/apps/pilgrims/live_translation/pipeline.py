import os
import tempfile
import wave

from django.conf import settings

from .domain import TranslationTurn
from .errors import FeatureDisabledError, ReadinessError
from .readiness import check_readiness
from .registry import registry
from .validation import validate_language, validate_text


class LocalLiveTranslationPipeline:
    def __init__(
        self,
        recognizer=None,
        translator=None,
        synthesizer=None,
        require_enabled=True,
        require_ready=True,
    ):
        self.recognizer = recognizer
        self.translator = translator
        self.synthesizer = synthesizer
        self.require_enabled = require_enabled
        self.require_ready = require_ready

    def _validate_available(self):
        if self.require_enabled and not settings.LOCAL_LIVE_TRANSLATION_ENABLED:
            raise FeatureDisabledError(
                "Local live translation is disabled. Set "
                "LOCAL_LIVE_TRANSLATION_ENABLED=1."
            )
        if self.require_ready:
            report = check_readiness()
            if not report.ready:
                commands = [issue.command for issue in report.issues if issue.command]
                raise ReadinessError(
                    "Local live translation is not ready. " + " ".join(commands)
                )

    def _recognizer(self):
        return self.recognizer or registry.get_recognizer()

    def _translator(self):
        return self.translator or registry.get_translator()

    def _synthesizer(self):
        return self.synthesizer or registry.get_synthesizer()

    def translate_text(self, text, source_language, target_language):
        self._validate_available()
        return self._translator().translate(
            validate_text(text),
            validate_language(source_language),
            validate_language(target_language),
        )

    def translate_text_stream(self, text, source_language, target_language):
        self._validate_available()
        yield from self._translator().translate_stream(
            validate_text(text),
            validate_language(source_language),
            validate_language(target_language),
        )

    def synthesize_text(self, text, language):
        self._validate_available()
        return self._synthesizer().synthesize(
            validate_text(text), validate_language(language)
        )

    def process_audio_turn(self, audio_path, target_language, source_language=None):
        self._validate_available()
        target_language = validate_language(target_language)
        source_language = (
            validate_language(source_language) if source_language else None
        )
        transcript = self._recognizer().transcribe(audio_path, source_language)
        translation = self._translator().translate(
            transcript.text, transcript.language, target_language
        )
        return TranslationTurn(transcript, translation)

    def process_finalized_pcm_utterance(
        self, pcm_bytes, source_language, target_language
    ):
        transcript = self.transcribe_pcm(pcm_bytes, source_language)
        translation = self.translate_text(
            transcript.text, transcript.language, target_language
        )
        return TranslationTurn(transcript, translation)

    def transcribe_pcm(self, pcm_bytes, source_language=None):
        self._validate_available()
        path = None
        config = settings.LOCAL_LIVE_TRANSLATION
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                path = tmp.name
            with wave.open(path, "wb") as wav_file:
                wav_file.setnchannels(config["REALTIME_CHANNELS"])
                wav_file.setsampwidth(config["REALTIME_SAMPLE_WIDTH_BYTES"])
                wav_file.setframerate(config["REALTIME_SAMPLE_RATE"])
                wav_file.writeframes(pcm_bytes)
            return self._recognizer().transcribe(path, source_language)
        finally:
            if path and os.path.exists(path):
                os.unlink(path)
