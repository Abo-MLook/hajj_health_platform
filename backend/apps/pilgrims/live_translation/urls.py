from django.urls import path

from . import views

app_name = "live_translation"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("readiness/", views.readiness, name="readiness"),
    path("text/", views.text_translation, name="text"),
    path("audio-turn/", views.audio_turn, name="audio_turn"),
    path("tts/", views.tts, name="tts"),
]
