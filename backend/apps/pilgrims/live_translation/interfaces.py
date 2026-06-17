from collections.abc import Iterable
from typing import Protocol

from .domain import SynthesizedAudioChunk, Transcript, TranslationResult


class SpeechRecognizer(Protocol):
    def transcribe(self, audio_path: str, language: str | None = None) -> Transcript:
        ...


class Translator(Protocol):
    def translate(
        self, text: str, source_language: str, target_language: str
    ) -> TranslationResult:
        ...

    def translate_stream(
        self, text: str, source_language: str, target_language: str
    ) -> Iterable[str]:
        ...


class SpeechSynthesizer(Protocol):
    def synthesize(self, text: str, language: str) -> SynthesizedAudioChunk:
        ...
