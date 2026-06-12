"""Import the synthetic triage dataset into the live Pilgrim + HealthProfile
tables so the mobile app and web dashboard (which both read /api/pilgrims/)
show a full roster instead of just the hand-seeded records.

Maps onto the EXISTING schema only — the dataset's vitals/triage columns
(BP, cholesterol, CVD risk, Triage_Category) are intentionally dropped because
there are no fields for them. The ICD condition flags and medication flags are
folded into the free-text diseases / medications fields the schema already has.

Usage:
    python manage.py import_triage_csv
    python manage.py import_triage_csv --limit 200
    python manage.py import_triage_csv --path /custom/path.csv
"""

import csv
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.pilgrims.models import HealthProfile, Pilgrim

# Default location: repo_root/hajj_triage_ai/data/hajj_dataset.csv
DEFAULT_CSV = settings.BASE_DIR.parent / "hajj_triage_ai" / "data" / "hajj_dataset.csv"

# ICD flag column → human-readable disease name (for diseases_text)
DISEASE_COLUMNS = {
    "ICD_E08_E13_Diabetes": "Diabetes Mellitus",
    "ICD_I10_I15_Hypertension": "Hypertension",
    "ICD_I20_I50_HeartDisease": "Heart Disease",
    "ICD_J40_J47_Respiratory": "Chronic Respiratory Disease",
    "ICD_N18_KidneyDisease": "Chronic Kidney Disease",
}

# Medication / support flag column → label (for medications_text)
MEDICATION_COLUMNS = {
    "Takes_Diuretics": "Diuretics",
    "Takes_Beta_Blockers": "Beta-Blockers",
    "Uses_Oxygen": "Supplemental Oxygen",
    "Needs_Walking_Assist": "Walking Assistance",
}

# Numeric columns the triage model consumes — coerced to float when we stash the
# feature vector so xgboost gets numbers, not CSV strings. (Gender is mapped by
# the model itself; the text/target columns are dropped by predict_hajj_triage.)
NUMERIC_FEATURES = [
    "Age", "BMI", "Systolic_BP", "Diastolic_BP", "Total_Cholesterol",
    "HDL_Cholesterol", "Num_Critical_Diseases", "ICD_E08_E13_Diabetes",
    "ICD_I10_I15_Hypertension", "ICD_I20_I50_HeartDisease",
    "ICD_J40_J47_Respiratory", "ICD_N18_KidneyDisease", "Smoker",
    "Needs_Walking_Assist", "Uses_Oxygen", "Takes_Diuretics",
    "Takes_Beta_Blockers", "CVD_Risk_Score",
]


def _build_feature_vector(row):
    """The exact dict shape predict_hajj_triage expects: numerics as floats,
    Gender/text passed through. Returns None if any numeric is unparseable."""
    feat = {}
    for key, value in row.items():
        if key in NUMERIC_FEATURES:
            try:
                feat[key] = float(value)
            except (TypeError, ValueError):
                feat[key] = None
        else:
            feat[key] = value
    return feat


def _is_set(value):
    return str(value).strip() in {"1", "1.0", "true", "True", "yes"}


def _dob_from_age(age_str):
    """Approximate a date_of_birth so Pilgrim.age renders. Returns None if the
    age is missing/unparseable."""
    try:
        age = int(float(age_str))
    except (TypeError, ValueError):
        return None
    today = date.today()
    try:
        return today.replace(year=today.year - age)
    except ValueError:  # Feb 29 → fall back to Feb 28
        return today.replace(year=today.year - age, day=28)


class Command(BaseCommand):
    help = "Import the hajj_triage_ai dataset into Pilgrim + HealthProfile."

    def add_arguments(self, parser):
        parser.add_argument("--path", type=str, default=str(DEFAULT_CSV))
        parser.add_argument("--limit", type=int, default=0, help="0 = all rows")

    def handle(self, *args, **options):
        csv_path = Path(options["path"])
        limit = options["limit"]
        if not csv_path.exists():
            raise CommandError(f"CSV not found: {csv_path}")

        created = updated = skipped = 0

        with csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            with transaction.atomic():
                for i, row in enumerate(reader):
                    if limit and i >= limit:
                        break

                    passport = (row.get("Passport_Number") or "").strip()
                    if not passport:
                        skipped += 1
                        continue

                    gender_raw = (row.get("Gender") or "").strip().upper()
                    gender = {"M": "male", "F": "female"}.get(gender_raw, "")

                    # Pilgrim is keyed on the unique passport number so re-runs
                    # update rather than duplicate.
                    pilgrim, was_created = Pilgrim.objects.update_or_create(
                        passport_number=passport,
                        defaults={
                            "full_name": (row.get("Fullname") or "").strip() or "Unknown",
                            "nationality": (row.get("Nationality") or "").strip(),
                            "gender": gender,
                            "date_of_birth": _dob_from_age(row.get("Age")),
                        },
                    )

                    diseases = [
                        name for col, name in DISEASE_COLUMNS.items() if _is_set(row.get(col))
                    ]
                    medications = [
                        name for col, name in MEDICATION_COLUMNS.items() if _is_set(row.get(col))
                    ]

                    HealthProfile.objects.update_or_create(
                        pilgrim=pilgrim,
                        defaults={
                            "diseases_text": ", ".join(diseases),
                            "medications_text": "; ".join(medications),
                            "allergies_text": "",
                            "vaccinations_text": "",
                            "status": "approved",
                            "confidence_score": 100,  # dataset is ground truth
                            # structured vector for the triage model
                            "triage_features": _build_feature_vector(row),
                        },
                    )

                    if was_created:
                        created += 1
                    else:
                        updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created} updated={updated} skipped={skipped} "
                f"(total pilgrims now {Pilgrim.objects.count()})"
            )
        )
