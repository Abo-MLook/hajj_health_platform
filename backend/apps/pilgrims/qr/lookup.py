from apps.pilgrims.models import HealthProfile, Pilgrim


def get_pilgrim_by_patient_id(patient_id):
    if not patient_id:
        return None
    return Pilgrim.objects.filter(patient_id=patient_id).first()


def get_health_profile_by_patient_id(patient_id):
    """Fetch the HealthProfile for the pilgrim matching patient_id.

    Returns None if no pilgrim matches, or if the matching pilgrim
    has no health profile yet.
    """
    pilgrim = get_pilgrim_by_patient_id(patient_id)
    if pilgrim is None:
        return None

    try:
        return pilgrim.health_profile
    except HealthProfile.DoesNotExist:
        return None
