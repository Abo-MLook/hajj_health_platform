import sys
from unittest.mock import patch

from django.test import TestCase


class DisabledFeatureTests(TestCase):
    def test_feature_is_disabled_by_default(self):
        from django.conf import settings

        self.assertFalse(settings.LOCAL_LIVE_TRANSLATION_ENABLED)

    def test_health_is_lightweight(self):
        with patch("urllib.request.urlopen") as urlopen:
            response = self.client.get("/api/live-translation/health/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["enabled"])
        urlopen.assert_not_called()

    def test_disabled_translation_returns_enablement_instruction(self):
        response = self.client.post(
            "/api/live-translation/text/",
            data='{"text":"hello","source_language":"en","target_language":"ar"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "feature_disabled")
        self.assertIn("LOCAL_LIVE_TRANSLATION_ENABLED=1", response.json()["message"])

    def test_disabled_readiness_does_not_import_or_contact_services(self):
        before = set(sys.modules)
        with patch("urllib.request.urlopen") as urlopen:
            response = self.client.get("/api/live-translation/readiness/")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["enabled"])
        self.assertNotIn("faster_whisper", set(sys.modules) - before)
        urlopen.assert_not_called()
