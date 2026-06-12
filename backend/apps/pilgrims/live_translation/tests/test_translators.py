from unittest.mock import MagicMock

from django.test import SimpleTestCase

from apps.pilgrims.live_translation.errors import TranslationError
from apps.pilgrims.live_translation.translators import OllamaTranslator


CONFIG = {
    "OLLAMA_URL": "http://127.0.0.1:11434",
    "ALLOW_NON_LOOPBACK_OLLAMA": False,
    "OLLAMA_MODEL": "qwen3.5:9b",
    "OLLAMA_TIMEOUT_SECONDS": 60,
    "OLLAMA_KEEP_ALIVE": -1,
    "OLLAMA_NUM_CTX": 512,
    "OLLAMA_NUM_PREDICT": 96,
}


class OllamaTranslatorTests(SimpleTestCase):
    def test_sync_payload_and_local_url(self):
        response = MagicMock()
        response.json.return_value = {"response": "مرحبا"}
        session = MagicMock()
        session.post.return_value = response
        result = OllamaTranslator(CONFIG, session).translate("hello", "en", "ar")
        self.assertEqual(result.translated_text, "مرحبا")
        url, = session.post.call_args.args
        payload = session.post.call_args.kwargs["json"]
        self.assertEqual(url, "http://127.0.0.1:11434/api/generate")
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["think"])
        self.assertEqual(payload["keep_alive"], -1)
        self.assertEqual(payload["options"]["temperature"], 0)
        self.assertEqual(payload["options"]["num_ctx"], 512)
        self.assertEqual(payload["options"]["num_predict"], 96)

    def test_stream_parses_ndjson(self):
        response = MagicMock()
        response.iter_lines.return_value = [
            '{"response":"one "}',
            '{"response":"two","done":true}',
        ]
        session = MagicMock()
        session.post.return_value = response
        chunks = list(
            OllamaTranslator(CONFIG, session).translate_stream("x", "en", "ar")
        )
        self.assertEqual(chunks, ["one ", "two"])
        self.assertTrue(session.post.call_args.kwargs["stream"])
        self.assertTrue(session.post.call_args.kwargs["json"]["stream"])

    def test_same_language_does_not_call_http(self):
        session = MagicMock()
        result = OllamaTranslator(CONFIG, session).translate("same", "en", "en")
        self.assertEqual(result.translated_text, "same")
        session.post.assert_not_called()

    def test_failures_and_empty_outputs_are_errors(self):
        session = MagicMock()
        session.post.side_effect = OSError("down")
        with self.assertRaises(TranslationError):
            OllamaTranslator(CONFIG, session).translate("x", "en", "ar")
        response = MagicMock()
        response.json.return_value = {"response": ""}
        session.post.side_effect = None
        session.post.return_value = response
        with self.assertRaises(TranslationError):
            OllamaTranslator(CONFIG, session).translate("x", "en", "ar")

    def test_malformed_stream_is_error(self):
        response = MagicMock()
        response.iter_lines.return_value = ["not json"]
        session = MagicMock()
        session.post.return_value = response
        with self.assertRaises(TranslationError):
            list(OllamaTranslator(CONFIG, session).translate_stream("x", "en", "ar"))
