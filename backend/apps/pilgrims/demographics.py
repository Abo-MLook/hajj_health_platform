import logging
from datetime import date

logger = logging.getLogger(__name__)

VALID_GENDERS = {"male", "female"}


def _parse_iso_date(value):
    """Parse a YYYY-MM-DD string into a date, rejecting impossible values."""
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed > date.today() or parsed.year < 1900:
        return None
    return parsed


def apply_demographics(document):
    """Fill the pilgrim's demographic fields from the document's extracted JSON.

    Only fills fields that are currently empty — never overwrites data that
    was entered manually or extracted from an earlier document.

    Returns the list of field names that were updated.
    """
    data = document.extracted_json or {}
    pilgrim = document.pilgrim
    updated = []

    if not pilgrim.date_of_birth:
        dob = _parse_iso_date(data.get("date_of_birth"))
        if dob:
            pilgrim.date_of_birth = dob
            updated.append("date_of_birth")

    if not pilgrim.gender:
        gender = (data.get("gender") or "").strip().lower()
        if gender in VALID_GENDERS:
            pilgrim.gender = gender
            updated.append("gender")

    if not pilgrim.nationality:
        nationality = (data.get("nationality") or "").strip()
        if nationality:
            pilgrim.nationality = nationality[:100]
            updated.append("nationality")

    if updated:
        pilgrim.save(update_fields=updated)
        logger.info("Demographics updated for pilgrim %s: %s", pilgrim.pk, updated)

    return updated
