import json
import os
import tempfile

from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .constants import PRIVACY_MODE, SUPPORTED_LANGUAGES
from .errors import LiveTranslationError
from .pipeline import LocalLiveTranslationPipeline
from .readiness import check_readiness
from .validation import validate_language


def _error(exc, status=400):
    code = getattr(exc, "code", "invalid_request")
    return JsonResponse({"ok": False, "error": code, "message": str(exc)}, status=status)


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Malformed JSON request body.")


@require_GET
def health(request):
    from django.conf import settings

    return JsonResponse(
        {
            "ok": True,
            "enabled": settings.LOCAL_LIVE_TRANSLATION_ENABLED,
            "privacy_mode": PRIVACY_MODE,
            "supported_languages": list(SUPPORTED_LANGUAGES),
            "voip_implemented": False,
            "realtime_core_implemented": True,
        }
    )


@require_GET
def readiness(request):
    report = check_readiness()
    return JsonResponse(report.to_dict(), status=200 if report.ready else 503)


@require_POST
def text_translation(request):
    try:
        payload = _json_body(request)
        result = LocalLiveTranslationPipeline().translate_text(
            payload.get("text"),
            payload.get("source_language"),
            payload.get("target_language"),
        )
        return JsonResponse(
            {
                "source_language": result.source_language,
                "target_language": result.target_language,
                "original_text": result.original_text,
                "translated_text": result.translated_text,
            }
        )
    except LiveTranslationError as exc:
        return _error(exc, 503 if exc.code in {"feature_disabled", "not_ready"} else 400)
    except (AttributeError, ValueError) as exc:
        return _error(exc)


@require_POST
def audio_turn(request):
    uploaded = request.FILES.get("audio")
    if not uploaded:
        return _error(ValueError("Missing multipart audio file."), 400)
    path = None
    try:
        target = validate_language(request.POST.get("target_language"))
        source = request.POST.get("source_language")
        source = validate_language(source) if source else None
        suffix = os.path.splitext(uploaded.name)[1] or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            path = tmp.name
            for chunk in uploaded.chunks():
                tmp.write(chunk)
        turn = LocalLiveTranslationPipeline().process_audio_turn(path, target, source)
        return JsonResponse(
            {
                "source_language": turn.transcript.language,
                "target_language": turn.translation.target_language,
                "transcript": turn.transcript.text,
                "translated_text": turn.translation.translated_text,
                "language_probability": turn.transcript.language_probability,
            }
        )
    except LiveTranslationError as exc:
        return _error(exc, 503 if exc.code in {"feature_disabled", "not_ready"} else 400)
    finally:
        if path and os.path.exists(path):
            os.unlink(path)


@require_POST
def tts(request):
    try:
        payload = _json_body(request)
        audio = LocalLiveTranslationPipeline().synthesize_text(
            payload.get("text"), payload.get("language")
        )
        response = FileResponse(
            iter([audio.wav_bytes]),
            content_type="audio/wav",
            filename=f"translation-{audio.language}.wav",
        )
        return response
    except LiveTranslationError as exc:
        return _error(exc, 503 if exc.code in {"feature_disabled", "not_ready"} else 400)
    except (AttributeError, ValueError) as exc:
        return _error(exc)
