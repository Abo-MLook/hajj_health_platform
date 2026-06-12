# Local Live Translation Backend

This is an optional backend-only, transport-independent scaffold. VoIP, SIP,
PSTN, WebRTC, signaling, sockets, media rooms, microphone capture, playback,
and audio-track publishing are intentionally not implemented.

The feature is off by default. Ordinary teammates can install
`requirements.txt`, start Django, and run unrelated tests without Whisper,
PyTorch, Transformers, NLLB, Ollama, espeak-ng, CUDA, or model downloads.

## Enable And Prepare

```bash
export LOCAL_LIVE_TRANSLATION_ENABLED=1
sudo pacman -S --needed ollama espeak-ng
python -m pip install -r requirements-live-translation.txt
ollama pull qwen3.5:9b
python manage.py live_translation_setup --download-whisper
python manage.py live_translation_setup --verify-ollama
python manage.py live_translation_setup --warm-ollama
python manage.py live_translation_setup --check
```

Run all explicit setup operations with:

```bash
python manage.py live_translation_setup --all
```

No model is downloaded during an HTTP request. There is no cloud fallback,
telemetry, analytics, or remote translation fallback. Ollama is restricted to
loopback unless `ALLOW_NON_LOOPBACK_OLLAMA=1` is explicitly set for a trusted
self-hosted server.

Supported languages are Arabic (`ar`), Persian (`fa`), Urdu (`ur`), and English
(`en`). Safety-sensitive screens should always display both original and
translated text.

## Real-Time Design

A future media worker will feed mono, signed 16-bit little-endian PCM at 16 kHz
in roughly 20 ms chunks. The in-memory core performs bounded energy-based
silence endpointing, detects and locks the remote caller language once,
transcribes locally, streams local translation text, groups meaningful phrases
for TTS, and emits transport-neutral events. The baseline detector can be
replaced by a stronger local VAD.

Whisper `small` on CPU INT8 is the default to reduce GPU contention while
`qwen3.5:9b` uses the developer's RTX 2060 SUPER. Both are configurable.
Whisper can be preloaded by a dedicated future worker. Ollama uses
`keep_alive=-1` and can be warmed explicitly.

espeak-ng is an offline baseline, not the expected final voice quality. A local
neural TTS engine can be evaluated later. NLLB is an optional local benchmark
path installed from `requirements-live-translation-nllb.txt`; its licensing,
production suitability, latency, and medical translation quality require
review.

## Development Endpoints

```bash
curl http://127.0.0.1:8000/api/live-translation/health/
curl http://127.0.0.1:8000/api/live-translation/readiness/
curl -X POST http://127.0.0.1:8000/api/live-translation/text/ \
  -H 'Content-Type: application/json' \
  -d '{"text":"من به بیمارستان نیاز دارم","source_language":"fa","target_language":"ar"}'
curl -X POST http://127.0.0.1:8000/api/live-translation/audio-turn/ \
  -F audio=@caller.wav -F target_language=ar -F source_language=fa
curl -X POST http://127.0.0.1:8000/api/live-translation/tts/ \
  -H 'Content-Type: application/json' \
  -d '{"text":"أحتاج إلى مستشفى","language":"ar"}' --output translation.wav
```

These are synchronous development endpoints. Real-time sockets are not part of
this package.

## Tests

```bash
python manage.py check
python manage.py test apps.pilgrims.live_translation
```

The tests use fakes and mocks. They do not contact Ollama, access the internet,
download models, load Whisper/PyTorch/Transformers, require espeak-ng, or
require a GPU.

## Troubleshooting

- Feature disabled: set `LOCAL_LIVE_TRANSLATION_ENABLED=1`.
- Missing Python dependency: run
  `python -m pip install -r requirements-live-translation.txt`.
- Missing cached Whisper model: run
  `python manage.py live_translation_setup --download-whisper`.
- Missing Ollama/espeak-ng on Arch: run
  `sudo pacman -S --needed ollama espeak-ng`.
- Ollama not started: run `ollama serve`.
- Missing model: run `ollama pull qwen3.5:9b`.
- Check all actionable issues with
  `python manage.py live_translation_setup --check`.

## Decisions Before VoIP Integration

- Browser-to-browser only, or SIP/PSTN too?
- Which self-hosted media server?
- Which language for the transport worker?
- Expected simultaneous calls?
- Turn-based first, or simultaneous conversation?
- What barge-in behavior?
- What transcript retention policy?
- What audio recording policy?
- What TTS quality is acceptable?
- What end-to-end latency target?
- What GPU deployment strategy?
- How should manual language override behave in the future UI?
