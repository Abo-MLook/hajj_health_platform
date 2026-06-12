from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str
    language_probability: float | None = None


@dataclass(frozen=True)
class TranslationResult:
    original_text: str
    translated_text: str
    source_language: str
    target_language: str


@dataclass(frozen=True)
class TranslationTurn:
    transcript: Transcript
    translation: TranslationResult


@dataclass(frozen=True)
class PcmAudioChunk:
    data: bytes
    sample_rate: int = 16000
    channels: int = 1
    sample_width_bytes: int = 2


@dataclass(frozen=True)
class FinalizedUtterance:
    pcm_bytes: bytes
    duration_ms: int
    speech_duration_ms: int


@dataclass(frozen=True)
class TranslationTextChunk:
    text: str
    final: bool = False


@dataclass(frozen=True)
class SynthesizedAudioChunk:
    wav_bytes: bytes
    language: str
    text: str


@dataclass
class RealtimeSessionState:
    session_id: str
    caller_language: str | None = None
    caller_language_overridden: bool = False


@dataclass(frozen=True)
class ReadinessIssue:
    code: str
    message: str
    command: str | None = None


@dataclass
class ReadinessReport:
    enabled: bool
    ready: bool
    privacy_mode: str
    issues: list[ReadinessIssue] = field(default_factory=list)
    translator_backend: str = ""
    ollama_url: str = ""
    ollama_model: str = ""
    whisper_model: str = ""
    tts_backend: str = ""
    voip_implemented: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class RealtimeEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)
