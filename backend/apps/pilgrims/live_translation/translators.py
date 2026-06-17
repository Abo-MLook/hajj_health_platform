import json

from django.conf import settings

from .constants import NLLB_LANGUAGE_CODES, SUPPORTED_LANGUAGES
from .domain import TranslationResult
from .errors import TranslationError
from .validation import validate_language, validate_ollama_url, validate_text


class OllamaTranslator:
    def __init__(self, config=None, session=None):
        self.config = config or settings.LOCAL_LIVE_TRANSLATION
        self.session = session

    def _requests(self):
        if self.session is not None:
            return self.session
        try:
            import requests
        except ImportError as exc:
            raise TranslationError(
                "requests is missing. Run: python -m pip install -r "
                "requirements-live-translation.txt"
            ) from exc
        return requests

    def _endpoint(self):
        base = validate_ollama_url(
            self.config["OLLAMA_URL"],
            self.config["ALLOW_NON_LOOPBACK_OLLAMA"],
        )
        return f"{base}/api/generate"

    def _prepare(self, text, source_language, target_language, stream):
        text = validate_text(text)
        source = validate_language(source_language)
        target = validate_language(target_language)
        prompt = (
            f"Translate {SUPPORTED_LANGUAGES[source]} to "
            f"{SUPPORTED_LANGUAGES[target]}.\n"
            "Return only the translated text.\n"
            f"Text:\n{text}"
        )
        payload = {
            "model": self.config["OLLAMA_MODEL"],
            "prompt": prompt,
            "stream": stream,
            "think": False,
            "keep_alive": self.config["OLLAMA_KEEP_ALIVE"],
            "options": {
                "temperature": 0,
                "num_ctx": self.config["OLLAMA_NUM_CTX"],
                "num_predict": self.config["OLLAMA_NUM_PREDICT"],
            },
        }
        return text, source, target, payload

    def translate(self, text, source_language, target_language):
        text, source, target, payload = self._prepare(
            text, source_language, target_language, False
        )
        if source == target:
            return TranslationResult(text, text, source, target)
        try:
            response = self._requests().post(
                self._endpoint(),
                json=payload,
                timeout=self.config["OLLAMA_TIMEOUT_SECONDS"],
            )
            response.raise_for_status()
            translated = response.json().get("response", "").strip()
        except Exception as exc:
            raise TranslationError(f"Local Ollama translation failed: {exc}") from exc
        if not translated:
            raise TranslationError("Local Ollama returned an empty translation.")
        return TranslationResult(text, translated, source, target)

    def translate_stream(self, text, source_language, target_language):
        text, source, target, payload = self._prepare(
            text, source_language, target_language, True
        )
        if source == target:
            yield text
            return
        try:
            response = self._requests().post(
                self._endpoint(),
                json=payload,
                timeout=self.config["OLLAMA_TIMEOUT_SECONDS"],
                stream=True,
            )
            response.raise_for_status()
            emitted = False
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except (TypeError, json.JSONDecodeError) as exc:
                    raise TranslationError("Malformed Ollama streaming response.") from exc
                if item.get("error"):
                    raise TranslationError(f"Ollama error: {item['error']}")
                chunk = item.get("response", "")
                if chunk:
                    emitted = True
                    yield chunk
            if not emitted:
                raise TranslationError("Local Ollama returned an empty translation.")
        except TranslationError:
            raise
        except Exception as exc:
            raise TranslationError(f"Local Ollama streaming failed: {exc}") from exc


class NllbTranslator:
    """Optional local benchmark adapter; production and licensing need review."""

    def __init__(self, config=None, tokenizer=None, model=None):
        self.config = config or settings.LOCAL_LIVE_TRANSLATION
        self._tokenizer = tokenizer
        self._model = model

    def initialize(self):
        if self._model is not None and self._tokenizer is not None:
            return
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise TranslationError(
                "Optional NLLB dependencies are missing. Run: "
                "python -m pip install -r requirements-live-translation-nllb.txt"
            ) from exc
        del torch
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.config["NLLB_MODEL"], local_files_only=True
            )
            self._model = AutoModelForSeq2SeqLM.from_pretrained(
                self.config["NLLB_MODEL"], local_files_only=True
            ).to(self.config["NLLB_DEVICE"])
        except Exception as exc:
            raise TranslationError(
                "The NLLB model is not cached locally. Use an explicit offline "
                "model setup step before selecting the NLLB backend."
            ) from exc

    def translate(self, text, source_language, target_language):
        text = validate_text(text)
        source = validate_language(source_language)
        target = validate_language(target_language)
        if source == target:
            return TranslationResult(text, text, source, target)
        self.initialize()
        self._tokenizer.src_lang = NLLB_LANGUAGE_CODES[source]
        inputs = self._tokenizer(text, return_tensors="pt").to(
            self.config["NLLB_DEVICE"]
        )
        output = self._model.generate(
            **inputs,
            forced_bos_token_id=self._tokenizer.convert_tokens_to_ids(
                NLLB_LANGUAGE_CODES[target]
            ),
        )
        translated = self._tokenizer.batch_decode(
            output, skip_special_tokens=True
        )[0].strip()
        if not translated:
            raise TranslationError("NLLB returned an empty translation.")
        return TranslationResult(text, translated, source, target)

    def translate_stream(self, text, source_language, target_language):
        yield self.translate(text, source_language, target_language).translated_text
