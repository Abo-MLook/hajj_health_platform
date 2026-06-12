import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ...readiness import check_readiness
from ...stt import FasterWhisperSpeechRecognizer
from ...validation import validate_ollama_url


class Command(BaseCommand):
    help = "Explicitly check and prepare local live translation dependencies."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true")
        parser.add_argument("--download-whisper", action="store_true")
        parser.add_argument("--verify-ollama", action="store_true")
        parser.add_argument("--warm-ollama", action="store_true")
        parser.add_argument("--all", action="store_true")

    def handle(self, *args, **options):
        selected = any(
            options[name]
            for name in (
                "check",
                "download_whisper",
                "verify_ollama",
                "warm_ollama",
                "all",
            )
        )
        run_all = options["all"]
        if options["check"] or not selected or run_all:
            self._check()
        if options["download_whisper"] or run_all:
            self._download_whisper()
        if options["verify_ollama"] or run_all:
            self._verify_ollama()
        if options["warm_ollama"] or run_all:
            self._warm_ollama()

    def _check(self):
        report = check_readiness(enabled=True)
        self.stdout.write(json.dumps(report.to_dict(), indent=2))
        if report.ready:
            self.stdout.write(self.style.SUCCESS("Local live translation is ready."))

    def _download_whisper(self):
        config = settings.LOCAL_LIVE_TRANSLATION
        recognizer = FasterWhisperSpeechRecognizer(
            config=config, require_setup_marker=False
        )
        try:
            recognizer.download_model()
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Whisper model '{config['WHISPER_MODEL']}' cached successfully."
            )
        )

    def _ollama_request(self, path, payload=None, timeout=None):
        config = settings.LOCAL_LIVE_TRANSLATION
        base = validate_ollama_url(
            config["OLLAMA_URL"], config["ALLOW_NON_LOOPBACK_OLLAMA"]
        )
        data = json.dumps(payload).encode("utf-8") if payload else None
        request = urllib.request.Request(
            f"{base}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" if data else "GET",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=timeout or config["OLLAMA_TIMEOUT_SECONDS"]
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            raise CommandError(
                f"Ollama request failed: {exc}. Start Ollama with: ollama serve"
            ) from exc

    def _verify_ollama(self):
        config = settings.LOCAL_LIVE_TRANSLATION
        payload = self._ollama_request("/api/tags", timeout=5)
        names = {
            item.get("name") or item.get("model")
            for item in payload.get("models", [])
        }
        if config["OLLAMA_MODEL"] not in names:
            raise CommandError(
                f"Missing Ollama model. Run: ollama pull {config['OLLAMA_MODEL']}"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Ollama model '{config['OLLAMA_MODEL']}' is installed."
            )
        )

    def _warm_ollama(self):
        config = settings.LOCAL_LIVE_TRANSLATION
        self._ollama_request(
            "/api/generate",
            {
                "model": config["OLLAMA_MODEL"],
                "prompt": "Reply OK.",
                "stream": False,
                "think": False,
                "keep_alive": config["OLLAMA_KEEP_ALIVE"],
                "options": {"num_predict": 2, "temperature": 0},
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Ollama model '{config['OLLAMA_MODEL']}' warmed with no user data."
            )
        )
