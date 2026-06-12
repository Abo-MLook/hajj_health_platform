import ipaddress
from urllib.parse import urlparse

from .constants import SUPPORTED_LANGUAGES
from .errors import ConfigurationError, InvalidRequestError, UnsupportedLanguageError


def validate_language(language: str) -> str:
    normalized = (language or "").strip().lower()
    if normalized not in SUPPORTED_LANGUAGES:
        supported = ", ".join(SUPPORTED_LANGUAGES)
        raise UnsupportedLanguageError(
            f"Unsupported language '{language}'. Supported languages: {supported}."
        )
    return normalized


def validate_text(text: str) -> str:
    normalized = (text or "").strip()
    if not normalized:
        raise InvalidRequestError("Text must not be empty.")
    return normalized


def validate_ollama_url(url: str, allow_non_loopback: bool = False) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigurationError(f"Invalid Ollama URL: {url}")
    if allow_non_loopback:
        return url.rstrip("/")
    host = parsed.hostname
    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = host == "localhost"
    if not is_loopback:
        raise ConfigurationError(
            "Ollama must use a loopback host unless "
            "ALLOW_NON_LOOPBACK_OLLAMA=True."
        )
    return url.rstrip("/")
