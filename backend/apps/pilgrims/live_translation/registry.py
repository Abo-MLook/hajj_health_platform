from django.conf import settings

from .errors import ConfigurationError


class LiveTranslationRegistry:
    def __init__(self):
        self.reset()

    def reset(self):
        self._recognizer = None
        self._translator = None
        self._synthesizer = None

    def configure(
        self, recognizer=None, translator=None, synthesizer=None
    ):
        self._recognizer = recognizer
        self._translator = translator
        self._synthesizer = synthesizer

    def configuration(self):
        config = settings.LOCAL_LIVE_TRANSLATION
        return {
            "enabled": settings.LOCAL_LIVE_TRANSLATION_ENABLED,
            "translator_backend": config["TRANSLATOR_BACKEND"],
            "whisper_model": config["WHISPER_MODEL"],
            "tts_backend": config["TTS_BACKEND"],
        }

    def get_recognizer(self):
        if self._recognizer is None:
            from .stt import FasterWhisperSpeechRecognizer

            self._recognizer = FasterWhisperSpeechRecognizer()
        return self._recognizer

    def get_translator(self):
        if self._translator is None:
            backend = settings.LOCAL_LIVE_TRANSLATION["TRANSLATOR_BACKEND"]
            if backend == "ollama":
                from .translators import OllamaTranslator

                self._translator = OllamaTranslator()
            elif backend == "nllb":
                from .translators import NllbTranslator

                self._translator = NllbTranslator()
            else:
                raise ConfigurationError(
                    f"Unsupported translator backend: {backend}."
                )
        return self._translator

    def get_synthesizer(self):
        if self._synthesizer is None:
            from .tts import EspeakNgSpeechSynthesizer

            self._synthesizer = EspeakNgSpeechSynthesizer()
        return self._synthesizer


registry = LiveTranslationRegistry()
