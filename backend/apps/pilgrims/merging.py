from .models import HealthProfile


def _collect_structured_data(documents):
    diseases = set()
    allergies = set()
    vaccinations = set()
    medications = {}
    conflicting_medications = set()
    
    vitals = {
        "height": None,
        "weight": None,
        "systolic_bp": None,
        "diastolic_bp": None,
        "total_cholesterol": None,
        "hdl_cholesterol": None,
        "smoker": None,
        "oxygen_usage": None,
    }

    # Iterate in reverse to prioritize more recent documents if sorted by ID
    for document in reversed(documents):
        data = document.extracted_json or {}

        diseases.update(name.strip() for name in data.get("diseases", []) if name and name.strip())
        allergies.update(name.strip() for name in data.get("allergies", []) if name and name.strip())
        vaccinations.update(name.strip() for name in data.get("vaccinations", []) if name and name.strip())

        for medication in data.get("medications", []):
            name = (medication.get("name") or "").strip()
            if not name:
                continue
            details = ((medication.get("dose") or "").strip(), (medication.get("frequency") or "").strip())
            if name in medications and medications[name] != details:
                conflicting_medications.add(name)
            medications[name] = details
            
        for key in vitals.keys():
            if vitals[key] is None and data.get(key) is not None:
                vitals[key] = data.get(key)

    return diseases, allergies, vaccinations, medications, conflicting_medications, vitals


def _format_medications_text(medications):
    entries = []
    for name in sorted(medications):
        dose, frequency = medications[name]
        details = " ".join(part for part in (dose, frequency) if part)
        entries.append(f"{name} ({details})" if details else name)
    return "; ".join(entries)


def merge_health_profile(pilgrim):
    """Combine structured data from all of a pilgrim's medical documents
    into their unified HealthProfile.

    Documents that were rejected or have no structured data are ignored.
    Medications with the same name but conflicting dose/frequency across
    documents mark the profile as needs_review.
    """
    documents = list(pilgrim.documents.exclude(extracted_json__isnull=True).exclude(status="rejected").order_by('id'))

    diseases, allergies, vaccinations, medications, conflicts, vitals = _collect_structured_data(documents)

    profile, _ = HealthProfile.objects.get_or_create(pilgrim=pilgrim)
    profile.diseases_text = ", ".join(sorted(diseases))
    profile.allergies_text = ", ".join(sorted(allergies))
    profile.vaccinations_text = ", ".join(sorted(vaccinations))
    profile.medications_text = _format_medications_text(medications)
    
    profile.height = vitals["height"]
    profile.weight = vitals["weight"]
    profile.systolic_bp = vitals["systolic_bp"]
    profile.diastolic_bp = vitals["diastolic_bp"]
    profile.total_cholesterol = vitals["total_cholesterol"]
    profile.hdl_cholesterol = vitals["hdl_cholesterol"]
    profile.smoker = vitals["smoker"]
    profile.uses_oxygen = vitals["oxygen_usage"]
    # Needs walking assist might need to come from flags as well, but we can assume null or inferred later.

    if conflicts:
        profile.status = "needs_review"
        profile.confidence_score = 0
    elif documents:
        profile.status = "pending"
        profile.confidence_score = round(sum(document.confidence_score for document in documents) / len(documents))
    else:
        profile.status = "pending"
        profile.confidence_score = 0

    profile.save(update_fields=[
        "diseases_text",
        "allergies_text",
        "vaccinations_text",
        "medications_text",
        "status",
        "confidence_score",
        "height", "weight", "systolic_bp", "diastolic_bp", 
        "total_cholesterol", "hdl_cholesterol", "smoker", "uses_oxygen",
        "updated_at",
    ])
    return profile
