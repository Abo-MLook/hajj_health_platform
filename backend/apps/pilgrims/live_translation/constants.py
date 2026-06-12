SUPPORTED_LANGUAGES = {
    "ar": "Arabic",
    "fa": "Persian",
    "ur": "Urdu",
    "en": "English",
}

LOCAL_OPERATOR_LANGUAGE = "ar"
PRIVACY_MODE = "local-only"

NLLB_LANGUAGE_CODES = {
    "ar": "arb_Arab",
    "fa": "pes_Arab",
    "ur": "urd_Arab",
    "en": "eng_Latn",
}

INSTALL_PYTHON_COMMAND = (
    "python -m pip install -r requirements-live-translation.txt"
)
INSTALL_NLLB_COMMAND = (
    "python -m pip install -r requirements-live-translation-nllb.txt"
)
INSTALL_ARCH_COMMAND = "sudo pacman -S --needed ollama espeak-ng"
START_OLLAMA_COMMAND = "ollama serve"
DOWNLOAD_WHISPER_COMMAND = (
    "python manage.py live_translation_setup --download-whisper"
)
