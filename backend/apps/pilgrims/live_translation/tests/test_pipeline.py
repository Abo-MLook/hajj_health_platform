import os

from django.test import SimpleTestCase

from apps.pilgrims.live_translation.pipeline import LocalLiveTranslationPipeline
from apps.pilgrims.live_translation.tests.fakes import (
    FakeRecognizer,
    FakeSynthesizer,
    FakeTranslator,
)


class PipelineTests(SimpleTestCase):
    def pipeline(self, language="fa"):
        return LocalLiveTranslationPipeline(
            FakeRecognizer(language=language),
            FakeTranslator(["translated"]),
            FakeSynthesizer(),
            require_enabled=False,
            require_ready=False,
        )

    def test_remote_languages_translate_to_arabic(self):
        for language in ("fa", "ur", "en"):
            turn = self.pipeline(language).process_finalized_pcm_utterance(
                b"\x01\x00" * 3200, None, "ar"
            )
            self.assertEqual(turn.transcript.language, language)
            self.assertEqual(turn.translation.target_language, "ar")

    def test_arabic_translates_back_to_caller_languages(self):
        for target in ("fa", "ur", "en"):
            turn = self.pipeline("ar").process_finalized_pcm_utterance(
                b"\x01\x00" * 3200, "ar", target
            )
            self.assertEqual(turn.translation.source_language, "ar")
            self.assertEqual(turn.translation.target_language, target)

    def test_pcm_temporary_wav_is_cleaned(self):
        recognizer = FakeRecognizer()
        pipeline = LocalLiveTranslationPipeline(
            recognizer,
            FakeTranslator(),
            FakeSynthesizer(),
            require_enabled=False,
            require_ready=False,
        )
        pipeline.transcribe_pcm(b"\x00\x00" * 3200)
        self.assertFalse(os.path.exists(recognizer.calls[0][0]))
