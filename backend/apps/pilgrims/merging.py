from .models import HealthProfile


def _collect_structured_data(documents):
    diseases = set()
    allergies = set()
    vaccinations = set()
    medications = {}
    conflicting_medications = set()

    for document in documents:
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

    return diseases, allergies, vaccinations, medications, conflicting_medications


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
    documents = list(pilgrim.documents.exclude(extracted_json__isnull=True).exclude(status="rejected"))

    diseases, allergies, vaccinations, medications, conflicts = _collect_structured_data(documents)

    profile, _ = HealthProfile.objects.get_or_create(pilgrim=pilgrim)
    profile.diseases_text = ", ".join(sorted(diseases))
    profile.allergies_text = ", ".join(sorted(allergies))
    profile.vaccinations_text = ", ".join(sorted(vaccinations))
    profile.medications_text = _format_medications_text(medications)

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
        "updated_at",
    ])
    return profile
