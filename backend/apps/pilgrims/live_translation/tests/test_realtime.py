from django.test import SimpleTestCase

from apps.pilgrims.live_translation.errors import RealtimeBufferError
from apps.pilgrims.live_translation.pipeline import LocalLiveTranslationPipeline
from apps.pilgrims.live_translation.realtime import (
    EnergyEndpointDetector,
    PhraseChunker,
    RealtimeTranslationSession,
)
from apps.pilgrims.live_translation.tests.fakes import (
    FakeRecognizer,
    FakeSynthesizer,
    FakeTranslator,
)


def pcm(amplitude, milliseconds):
    samples = int(16000 * milliseconds / 1000)
    return int(amplitude).to_bytes(2, "little", signed=True) * samples


class EndpointDetectorTests(SimpleTestCase):
    def test_speech_silence_short_noise_flush_and_bounds(self):
        detector = EnergyEndpointDetector(min_speech_ms=40, end_silence_ms=40)
        self.assertTrue(detector.consume(pcm(2000, 20)).speech_started)
        update = detector.consume(pcm(2000, 20))
        self.assertIsNone(update.finalized)
        detector.consume(pcm(0, 20))
        finalized = detector.consume(pcm(0, 20)).finalized
        self.assertIsNotNone(finalized)
        self.assertGreater(len(finalized.pcm_bytes), 0)

        short = EnergyEndpointDetector(min_speech_ms=40, end_silence_ms=20)
        short.consume(pcm(2000, 20))
        self.assertIsNone(short.consume(pcm(0, 20)).finalized)

        flushed = EnergyEndpointDetector(min_speech_ms=20)
        flushed.consume(pcm(2000, 20))
        self.assertIsNotNone(flushed.flush())

        bounded = EnergyEndpointDetector(max_buffer_bytes=10)
        with self.assertRaises(RealtimeBufferError):
            bounded.consume(pcm(2000, 20))

    def test_phrase_chunking(self):
        chunker = PhraseChunker(3)
        self.assertEqual(chunker.add("one two three"), ["one two three"])
        self.assertEqual(chunker.add("hello, rest"), ["hello,"])
        self.assertEqual(chunker.flush(), ["rest"])


class RealtimeSessionTests(SimpleTestCase):
    def pipeline(self, language="fa", chunks=None):
        return LocalLiveTranslationPipeline(
            FakeRecognizer(language=language, text="caller text"),
            FakeTranslator(chunks or ["word one ", "word two."]),
            FakeSynthesizer(),
            require_enabled=False,
            require_ready=False,
        )

    def test_detects_locks_streams_and_reverses(self):
        session = RealtimeTranslationSession(self.pipeline(), config={
            "REALTIME_SAMPLE_RATE": 16000,
            "REALTIME_SAMPLE_WIDTH_BYTES": 2,
            "REALTIME_MIN_SPEECH_MS": 20,
            "REALTIME_END_SILENCE_MS": 20,
            "REALTIME_MAX_UTTERANCE_SECONDS": 20,
            "REALTIME_MAX_BUFFER_BYTES": 100000,
            "REALTIME_TRANSLATION_PHRASE_WORDS": 3,
            "TTS_ENABLED": True,
        })
        session.push_remote_pcm_chunk(pcm(2000, 20))
        events = session.push_remote_pcm_chunk(pcm(0, 20))
        types = [event.type for event in events]
        self.assertIn("caller_language_locked", types)
        self.assertEqual(session.state.caller_language, "fa")
        self.assertEqual(types.count("translation_chunk"), 2)
        self.assertIn("tts_phrase_ready", types)

        session.pipeline.recognizer.language = "ar"
        session.push_local_arabic_pcm_chunk(pcm(2000, 20))
        reverse = session.push_local_arabic_pcm_chunk(pcm(0, 20))
        completed = next(e for e in reverse if e.type == "translation_completed")
        self.assertEqual(completed.data["source_language"], "ar")
        self.assertEqual(completed.data["target_language"], "fa")

    def test_manual_override_replaces_detection(self):
        session = RealtimeTranslationSession(self.pipeline("fa"))
        session.set_caller_language_override("ur")
        self.assertEqual(session.state.caller_language, "ur")
        self.assertTrue(session.state.caller_language_overridden)
