import importlib.util
import json
import shutil
import urllib.error
import urllib.request

from django.conf import settings

from .constants import (
    DOWNLOAD_WHISPER_COMMAND,
    INSTALL_ARCH_COMMAND,
    INSTALL_NLLB_COMMAND,
    INSTALL_PYTHON_COMMAND,
    PRIVACY_MODE,
    START_OLLAMA_COMMAND,
)
from .domain import ReadinessIssue, ReadinessReport
from .errors import ConfigurationError
from .stt import whisper_setup_marker
from .validation import validate_ollama_url


def _config():
    return settings.LOCAL_LIVE_TRANSLATION


def check_readiness(enabled=None, contact_ollama=True):
    config = _config()
    enabled = (
        settings.LOCAL_LIVE_TRANSLATION_ENABLED if enabled is None else enabled
    )
    report = ReadinessReport(
        enabled=enabled,
        ready=False,
        privacy_mode=PRIVACY_MODE,
        translator_backend=config["TRANSLATOR_BACKEND"],
        ollama_url=config["OLLAMA_URL"],
        ollama_model=config["OLLAMA_MODEL"],
        whisper_model=config["WHISPER_MODEL"],
        tts_backend=config["TTS_BACKEND"],
    )
    if not enabled:
        report.issues.append(
            ReadinessIssue(
                "feature_disabled",
                "Local live translation is disabled.",
                "LOCAL_LIVE_TRANSLATION_ENABLED=1",
            )
        )
        return report

    missing_python = [
        module
        for module in ("faster_whisper", "requests")
        if importlib.util.find_spec(module) is None
    ]
    if missing_python:
        report.issues.append(
            ReadinessIssue(
                "missing_python_dependencies",
                f"Missing Python dependencies: {', '.join(missing_python)}.",
                INSTALL_PYTHON_COMMAND,
            )
        )

    backend = config["TRANSLATOR_BACKEND"]
    if backend == "nllb":
        missing = [
            name
            for name in ("torch", "transformers", "sentencepiece")
            if importlib.util.find_spec(name) is None
        ]
        if missing:
            report.issues.append(
                ReadinessIssue(
                    "missing_nllb_dependencies",
                    f"Missing optional NLLB dependencies: {', '.join(missing)}.",
                    INSTALL_NLLB_COMMAND,
                )
            )
    elif backend != "ollama":
        report.issues.append(
            ReadinessIssue(
                "invalid_translator_backend",
                f"Unsupported translator backend: {backend}.",
            )
        )

    if config["TTS_ENABLED"] and not shutil.which(config["ESPEAK_NG_EXECUTABLE"]):
        report.issues.append(
            ReadinessIssue(
                "missing_espeak_ng",
                "espeak-ng is not installed or not on PATH.",
                INSTALL_ARCH_COMMAND,
            )
        )

    if backend == "ollama":
        try:
            base_url = validate_ollama_url(
                config["OLLAMA_URL"], config["ALLOW_NON_LOOPBACK_OLLAMA"]
            )
        except ConfigurationError as exc:
            report.issues.append(ReadinessIssue("invalid_ollama_url", str(exc)))
        else:
            if contact_ollama:
                _check_ollama(report, base_url, config)

    if not any(issue.code == "missing_whisper_cache" for issue in report.issues):
        if not whisper_setup_marker(config["WHISPER_MODEL"]).exists():
            report.issues.append(
                ReadinessIssue(
                    "missing_whisper_cache",
                    "The configured Whisper model has not been explicitly cached.",
                    DOWNLOAD_WHISPER_COMMAND,
                )
            )

    report.ready = not report.issues
    return report


def _check_ollama(report, base_url, config):
    request = urllib.request.Request(f"{base_url}/api/tags", method="GET")
    try:
        with urllib.request.urlopen(
            request, timeout=min(config["OLLAMA_TIMEOUT_SECONDS"], 5)
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError) as exc:
        report.issues.append(
            ReadinessIssue(
                "ollama_unreachable",
                f"Ollama is not reachable at {base_url}: {exc}",
                START_OLLAMA_COMMAND,
            )
        )
        return
    names = {
        model.get("name") or model.get("model")
        for model in payload.get("models", [])
        if isinstance(model, dict)
    }
    if config["OLLAMA_MODEL"] not in names:
        report.issues.append(
            ReadinessIssue(
                "missing_ollama_model",
                f"Ollama model {config['OLLAMA_MODEL']} is not installed.",
                f"ollama pull {config['OLLAMA_MODEL']}",
            )
        )
