import os
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.pilgrims.live_translation.registry import registry
from apps.pilgrims.live_translation.tests.fakes import (
    FakeRecognizer,
    FakeSynthesizer,
    FakeTranslator,
    ReadyReport,
)


@override_settings(LOCAL_LIVE_TRANSLATION_ENABLED=True)
class ViewTests(TestCase):
    def setUp(self):
        registry.configure(FakeRecognizer(), FakeTranslator(), FakeSynthesizer())
        self.ready = patch(
            "apps.pilgrims.live_translation.pipeline.check_readiness",
            return_value=ReadyReport(),
        )
        self.ready.start()

    def tearDown(self):
        self.ready.stop()
        registry.reset()

    def test_health_contract(self):
        data = self.client.get("/api/live-translation/health/").json()
        self.assertEqual(data["privacy_mode"], "local-only")
        self.assertFalse(data["voip_implemented"])
        self.assertTrue(data["realtime_core_implemented"])

    def test_text_audio_and_tts_endpoints(self):
        text = self.client.post(
            "/api/live-translation/text/",
            data='{"text":"hello","source_language":"en","target_language":"ar"}',
            content_type="application/json",
        )
        self.assertEqual(text.status_code, 200)
        self.assertEqual(text.json()["translated_text"], "translated text")

        audio = self.client.post(
            "/api/live-translation/audio-turn/",
            {
                "audio": SimpleUploadedFile("caller.wav", b"RIFFfake"),
                "target_language": "ar",
                "source_language": "fa",
            },
        )
        self.assertEqual(audio.status_code, 200)
        self.assertEqual(audio.json()["source_language"], "fa")
        self.assertFalse(os.path.exists(registry.get_recognizer().calls[-1][0]))

        tts = self.client.post(
            "/api/live-translation/tts/",
            data='{"text":"hello","language":"en"}',
            content_type="application/json",
        )
        self.assertEqual(tts.status_code, 200)
        self.assertEqual(tts["Content-Type"], "audio/wav")

    def test_bad_requests(self):
        missing = self.client.post(
            "/api/live-translation/audio-turn/", {"target_language": "ar"}
        )
        self.assertEqual(missing.status_code, 400)
        unsupported = self.client.post(
            "/api/live-translation/text/",
            data='{"text":"x","source_language":"fr","target_language":"ar"}',
            content_type="application/json",
        )
        self.assertEqual(unsupported.status_code, 400)
        malformed = self.client.post(
            "/api/live-translation/text/",
            data="{",
            content_type="application/json",
        )
        self.assertEqual(malformed.status_code, 400)
