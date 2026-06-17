from types import SimpleNamespace

from apps.pilgrims.live_translation.domain import (
    SynthesizedAudioChunk,
    Transcript,
    TranslationResult,
)


class FakeRecognizer:
    def __init__(self, language="fa", text="spoken text", probability=0.9):
        self.language = language
        self.text = text
        self.probability = probability
        self.calls = []

    def transcribe(self, audio_path, language=None):
        self.calls.append((audio_path, language))
        return Transcript(self.text, language or self.language, self.probability)


class FakeTranslator:
    def __init__(self, chunks=None):
        self.chunks = chunks or ["translated text"]
        self.calls = []

    def translate(self, text, source_language, target_language):
        self.calls.append((text, source_language, target_language))
        translated = text if source_language == target_language else "".join(self.chunks)
        return TranslationResult(text, translated, source_language, target_language)

    def translate_stream(self, text, source_language, target_language):
        self.calls.append((text, source_language, target_language))
        if source_language == target_language:
            yield text
        else:
            yield from self.chunks


class FakeSynthesizer:
    def __init__(self):
        self.calls = []

    def synthesize(self, text, language):
        self.calls.append((text, language))
        return SynthesizedAudioChunk(b"RIFFfake", language, text)


class FakeWhisperModel:
    def __init__(self, text=" hello ", language="fa", probability=0.8):
        self.text = text
        self.language = language
        self.probability = probability
        self.kwargs = None

    def transcribe(self, path, **kwargs):
        self.kwargs = kwargs
        return [SimpleNamespace(text=self.text)], SimpleNamespace(
            language=self.language, language_probability=self.probability
        )


class ReadyReport:
    ready = True
    issues = []
