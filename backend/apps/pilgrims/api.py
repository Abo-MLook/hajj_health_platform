"""Read-only JSON API over the existing pilgrim records.

This is the connective tissue between the backend and the two clients:
  - the mobile app (`/api/pilgrims/<id>/`, called on bracelet QR scan)
  - the web ops dashboard (`/api/pilgrims/` list + detail)

It exposes the data we already have (Pilgrim + HealthProfile) — it does not
add new models or pipelines. GET-only, so a single `Access-Control-Allow-Origin`
header is enough for the browser dashboard (no preflight on simple requests).
"""

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Pilgrim


def _cors(response):
    """Allow the browser dashboard (different origin/port) to read these."""
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response


def _serialize_pilgrim(pilgrim):
    """Shape matches the mobile app's RemotePilgrim contract, plus the extra
    demographic fields the dashboard uses (age/gender/date_of_birth)."""
    profile = getattr(pilgrim, "health_profile", None)
    health_profile = None
    if profile is not None:
        health_profile = {
            "status": profile.status,
            "confidence_score": profile.confidence_score,
            "diseases": profile.diseases_text,
            "medications": profile.medications_text,
            "allergies": profile.allergies_text,
            "vaccinations": profile.vaccinations_text,
        }
    return {
        "patient_id": pilgrim.patient_id,
        "full_name": pilgrim.full_name,
        "nationality": pilgrim.nationality,
        "passport_number": pilgrim.passport_number,
        "gender": pilgrim.gender,
        "age": pilgrim.age,
        "date_of_birth": (
            pilgrim.date_of_birth.isoformat() if pilgrim.date_of_birth else None
        ),
        "health_profile": health_profile,
    }


@require_http_methods(["GET", "OPTIONS"])
def pilgrim_list(request):
    """All pilgrims, newest first. Optional ?q= filters by name / id / passport
    / nationality so the dashboard search can hit the server."""
    if request.method == "OPTIONS":
        return _cors(JsonResponse({}))

    pilgrims = Pilgrim.objects.select_related("health_profile").order_by("-created_at")

    query = (request.GET.get("q") or "").strip()
    if query:
        pilgrims = pilgrims.filter(
            Q(full_name__icontains=query)
            | Q(patient_id__icontains=query)
            | Q(passport_number__icontains=query)
            | Q(nationality__icontains=query)
        )

    results = [_serialize_pilgrim(p) for p in pilgrims]
    return _cors(JsonResponse({"count": len(results), "results": results}))


@require_http_methods(["GET", "OPTIONS"])
def pilgrim_triage(request, patient_id):
    """Real risk classification from the hajj_triage_ai model. Returns the model
    status (Green/Orange/Red), a normalized risk_level, vitals, conditions, and
    SHAP-ranked risk factors. `insufficient_data` when we have no feature vector
    for this pilgrim (e.g. a document-upload profile with only free text)."""
    if request.method == "OPTIONS":
        return _cors(JsonResponse({}))

    pilgrim = (
        Pilgrim.objects.select_related("health_profile")
        .filter(Q(patient_id=patient_id) | Q(passport_number=patient_id))
        .first()
    )
    if pilgrim is None:
        return _cors(JsonResponse({"error": "Pilgrim not found"}, status=404))

    profile = getattr(pilgrim, "health_profile", None)
    features = getattr(profile, "triage_features", None) if profile else None
    if not features:
        return _cors(JsonResponse({"status": "insufficient_data", "risk_level": None}))

    # Lazy import keeps xgboost/shap out of normal request/startup paths.
    from .triage import run_triage

    try:
        result = run_triage(features)
    except Exception as exc:  # model/feature mismatch — report, don't 500
        return _cors(
            JsonResponse(
                {"status": "triage_failed", "risk_level": None, "detail": str(exc)},
                status=200,
            )
        )

    result["patient_id"] = pilgrim.patient_id
    return _cors(JsonResponse(result))


@require_http_methods(["GET", "OPTIONS"])
def pilgrim_detail(request, patient_id):
    """A single pilgrim. The bracelet QR encodes the id, which may equal either
    the generated patient_id or the passport_number — accept both."""
    if request.method == "OPTIONS":
        return _cors(JsonResponse({}))

    pilgrim = (
        Pilgrim.objects.select_related("health_profile")
        .filter(Q(patient_id=patient_id) | Q(passport_number=patient_id))
        .first()
    )
    if pilgrim is None:
        return _cors(JsonResponse({"error": "Pilgrim not found"}, status=404))

    return _cors(JsonResponse(_serialize_pilgrim(pilgrim)))
