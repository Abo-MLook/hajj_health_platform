import re
import sys
import uuid
from array import array
from dataclasses import dataclass

from django.conf import settings

from .constants import LOCAL_OPERATOR_LANGUAGE
from .domain import FinalizedUtterance, RealtimeEvent, RealtimeSessionState
from .errors import RealtimeBufferError
from .validation import validate_language


@dataclass(frozen=True)
class EndpointUpdate:
    speech_started: bool = False
    finalized: FinalizedUtterance | None = None


class EnergyEndpointDetector:
    """Deterministic RMS baseline that can later be replaced by a local VAD."""

    def __init__(
        self,
        sample_rate=16000,
        sample_width_bytes=2,
        min_speech_ms=200,
        end_silence_ms=500,
        max_utterance_seconds=20,
        max_buffer_bytes=1000000,
        energy_threshold=500,
    ):
        self.sample_rate = sample_rate
        self.sample_width_bytes = sample_width_bytes
        self.min_speech_ms = min_speech_ms
        self.end_silence_ms = end_silence_ms
        self.max_utterance_ms = max_utterance_seconds * 1000
        self.max_buffer_bytes = max_buffer_bytes
        self.energy_threshold = energy_threshold
        self.reset()

    def reset(self):
        self._buffer = bytearray()
        self._speech_started = False
        self._speech_ms = 0
        self._silence_ms = 0
        self._total_ms = 0

    def _duration_ms(self, pcm_bytes):
        frame_bytes = self.sample_width_bytes
        return int(len(pcm_bytes) / frame_bytes / self.sample_rate * 1000)

    def consume(self, pcm_bytes):
        if not isinstance(pcm_bytes, bytes) or not pcm_bytes:
            raise RealtimeBufferError("PCM chunk must be non-empty bytes.")
        if len(pcm_bytes) % self.sample_width_bytes:
            raise RealtimeBufferError("PCM chunk is not aligned to 16-bit samples.")
        duration_ms = self._duration_ms(pcm_bytes)
        samples = array("h")
        samples.frombytes(pcm_bytes)
        if sys.byteorder != "little":
            samples.byteswap()
        rms = int((sum(sample * sample for sample in samples) / len(samples)) ** 0.5)
        is_speech = rms >= self.energy_threshold
        just_started = False
        if not self._speech_started:
            if not is_speech:
                return EndpointUpdate()
            self._speech_started = True
            just_started = True
        if len(self._buffer) + len(pcm_bytes) > self.max_buffer_bytes:
            self.reset()
            raise RealtimeBufferError("Maximum real-time PCM buffer size exceeded.")
        self._buffer.extend(pcm_bytes)
        self._total_ms += duration_ms
        if is_speech:
            self._speech_ms += duration_ms
            self._silence_ms = 0
        else:
            self._silence_ms += duration_ms
        if (
            self._silence_ms >= self.end_silence_ms
            or self._total_ms >= self.max_utterance_ms
        ):
            return EndpointUpdate(just_started, self._finalize())
        return EndpointUpdate(just_started)

    def flush(self):
        if not self._speech_started:
            return None
        return self._finalize()

    def _finalize(self):
        utterance = None
        if self._speech_ms >= self.min_speech_ms:
            utterance = FinalizedUtterance(
                bytes(self._buffer), self._total_ms, self._speech_ms
            )
        self.reset()
        return utterance

    @property
    def buffered_bytes(self):
        return len(self._buffer)


class PhraseChunker:
    def __init__(self, word_threshold=6):
        self.word_threshold = word_threshold
        self.buffer = ""

    def add(self, text):
        self.buffer += text
        phrases = []
        while True:
            punctuation = re.search(r"[.!?؟،,;؛:]\s*", self.buffer)
            words = list(re.finditer(r"\S+", self.buffer))
            if punctuation:
                end = punctuation.end()
            elif len(words) >= self.word_threshold:
                end = words[self.word_threshold - 1].end()
            else:
                break
            phrase = self.buffer[:end].strip()
            self.buffer = self.buffer[end:].lstrip()
            if phrase:
                phrases.append(phrase)
        return phrases

    def flush(self):
        phrase = self.buffer.strip()
        self.buffer = ""
        return [phrase] if phrase else []


class RealtimeTranslationSession:
    def __init__(
        self,
        pipeline,
        config=None,
        remote_detector=None,
        local_detector=None,
        session_id=None,
    ):
        self.pipeline = pipeline
        self.config = config or settings.LOCAL_LIVE_TRANSLATION
        self.state = RealtimeSessionState(session_id or str(uuid.uuid4()))
        detector_kwargs = {
            "sample_rate": self.config["REALTIME_SAMPLE_RATE"],
            "sample_width_bytes": self.config["REALTIME_SAMPLE_WIDTH_BYTES"],
            "min_speech_ms": self.config["REALTIME_MIN_SPEECH_MS"],
            "end_silence_ms": self.config["REALTIME_END_SILENCE_MS"],
            "max_utterance_seconds": self.config[
                "REALTIME_MAX_UTTERANCE_SECONDS"
            ],
            "max_buffer_bytes": self.config["REALTIME_MAX_BUFFER_BYTES"],
        }
        self.remote_detector = remote_detector or EnergyEndpointDetector(**detector_kwargs)
        self.local_detector = local_detector or EnergyEndpointDetector(**detector_kwargs)

    def set_caller_language_override(self, language):
        self.state.caller_language = validate_language(language) if language else None
        self.state.caller_language_overridden = language is not None

    def push_remote_pcm_chunk(self, pcm_bytes):
        return self._push(self.remote_detector, pcm_bytes, "remote")

    def push_local_arabic_pcm_chunk(self, pcm_bytes):
        return self._push(self.local_detector, pcm_bytes, "local")

    def flush_remote(self):
        utterance = self.remote_detector.flush()
        return self.process_finalized_remote_utterance(utterance) if utterance else []

    def flush_local(self):
        utterance = self.local_detector.flush()
        return self.process_finalized_local_utterance(utterance) if utterance else []

    def _push(self, detector, pcm_bytes, direction):
        try:
            update = detector.consume(pcm_bytes)
            events = []
            if update.speech_started:
                events.append(RealtimeEvent("speech_started", {"direction": direction}))
            if update.finalized:
                processor = (
                    self.process_finalized_remote_utterance
                    if direction == "remote"
                    else self.process_finalized_local_utterance
                )
                events.extend(processor(update.finalized))
            return events
        except Exception as exc:
            return [RealtimeEvent("error", {"direction": direction, "message": str(exc)})]

    def process_finalized_remote_utterance(self, utterance):
        return self._process(
            utterance,
            source_language=self.state.caller_language,
            target_language=LOCAL_OPERATOR_LANGUAGE,
            direction="remote",
            detect_and_lock=self.state.caller_language is None,
        )

    def process_finalized_local_utterance(self, utterance):
        if not self.state.caller_language:
            return [
                RealtimeEvent(
                    "error",
                    {
                        "direction": "local",
                        "message": "Caller language must be locked before reverse translation.",
                    },
                )
            ]
        return self._process(
            utterance,
            source_language=LOCAL_OPERATOR_LANGUAGE,
            target_language=self.state.caller_language,
            direction="local",
            detect_and_lock=False,
        )

    def _process(
        self, utterance, source_language, target_language, direction, detect_and_lock
    ):
        events = [
            RealtimeEvent(
                "utterance_finalized",
                {"direction": direction, "duration_ms": utterance.duration_ms},
            )
        ]
        try:
            transcript = self.pipeline.transcribe_pcm(
                utterance.pcm_bytes, source_language
            )
            events.append(
                RealtimeEvent(
                    "transcript_ready",
                    {
                        "direction": direction,
                        "text": transcript.text,
                        "language": transcript.language,
                        "language_probability": transcript.language_probability,
                    },
                )
            )
            if detect_and_lock:
                self.state.caller_language = transcript.language
                events.append(
                    RealtimeEvent(
                        "caller_language_locked",
                        {"language": transcript.language, "automatic": True},
                    )
                )
            chunker = PhraseChunker(
                self.config["REALTIME_TRANSLATION_PHRASE_WORDS"]
            )
            translated_parts = []
            for chunk in self.pipeline.translate_text_stream(
                transcript.text, transcript.language, target_language
            ):
                translated_parts.append(chunk)
                events.append(
                    RealtimeEvent(
                        "translation_chunk",
                        {"direction": direction, "text": chunk},
                    )
                )
                for phrase in chunker.add(chunk):
                    events.extend(self._tts_events(phrase, target_language, direction))
            for phrase in chunker.flush():
                events.extend(self._tts_events(phrase, target_language, direction))
            events.append(
                RealtimeEvent(
                    "translation_completed",
                    {
                        "direction": direction,
                        "text": "".join(translated_parts).strip(),
                        "source_language": transcript.language,
                        "target_language": target_language,
                    },
                )
            )
        except Exception as exc:
            events.append(
                RealtimeEvent(
                    "error", {"direction": direction, "message": str(exc)}
                )
            )
        return events

    def _tts_events(self, phrase, language, direction):
        if not self.config["TTS_ENABLED"]:
            return []
        audio = self.pipeline.synthesize_text(phrase, language)
        return [
            RealtimeEvent(
                "tts_phrase_ready",
                {
                    "direction": direction,
                    "text": phrase,
                    "language": language,
                    "wav_bytes": audio.wav_bytes,
                },
            )
        ]
