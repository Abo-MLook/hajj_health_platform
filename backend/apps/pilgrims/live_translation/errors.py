class LiveTranslationError(Exception):
    code = "live_translation_error"


class FeatureDisabledError(LiveTranslationError):
    code = "feature_disabled"


class ConfigurationError(LiveTranslationError):
    code = "configuration_error"


class ReadinessError(LiveTranslationError):
    code = "not_ready"


class UnsupportedLanguageError(LiveTranslationError):
    code = "unsupported_language"


class SpeechRecognitionError(LiveTranslationError):
    code = "speech_recognition_error"


class TranslationError(LiveTranslationError):
    code = "translation_error"


class SynthesisError(LiveTranslationError):
    code = "synthesis_error"


class InvalidRequestError(LiveTranslationError):
    code = "invalid_request"


class RealtimeBufferError(LiveTranslationError):
    code = "realtime_buffer_error"
