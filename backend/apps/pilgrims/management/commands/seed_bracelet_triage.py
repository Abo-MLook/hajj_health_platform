"""Attach triage feature vectors to the demo bracelet pilgrims.

The hand-seeded bracelet pilgrims (the SA-2024-* ids the mobile app's QR codes
encode) only have free-text profiles, so the triage model returns
`insufficient_data` for them and a real scan can't show a classification.

This stamps each one with a clinically-consistent feature vector (aligned with
their known conditions/age) so a live QR scan demonstrates the model. Values are
tuned so the model returns the intended category. Idempotent.

Usage:  python manage.py seed_bracelet_triage
"""

from django.core.management.base import BaseCommand

from apps.pilgrims.models import HealthProfile, Pilgrim

# Full feature vector per bracelet id. Gender as M/F (the model maps it).
BRACELET_FEATURES = {
    # فاطمة عبدالله سيدي — 74, diabetes + heart + hypertension → Red
    "SA-2024-NG-07231": {
        "Fullname": "Fatima Abdullah Sidi", "Nationality": "Nigeria", "Gender": "F",
        "Age": 74.0, "BMI": 31.5, "Systolic_BP": 168.0, "Diastolic_BP": 96.0,
        "Total_Cholesterol": 255.0, "HDL_Cholesterol": 36.0, "Num_Critical_Diseases": 3.0,
        "ICD_E08_E13_Diabetes": 1.0, "ICD_I10_I15_Hypertension": 1.0,
        "ICD_I20_I50_HeartDisease": 1.0, "ICD_J40_J47_Respiratory": 0.0,
        "ICD_N18_KidneyDisease": 0.0, "Smoker": 0.0, "Needs_Walking_Assist": 1.0,
        "Uses_Oxygen": 1.0, "Takes_Diuretics": 1.0, "Takes_Beta_Blockers": 1.0,
        "CVD_Risk_Score": 42.0,
    },
    # محمد إبراهيم الفارسي — 68, heart + hypertension, smoker → Red
    "SA-2024-EG-04412": {
        "Fullname": "Mohammed Ibrahim Al-Farsi", "Nationality": "Egypt", "Gender": "M",
        "Age": 68.0, "BMI": 29.4, "Systolic_BP": 159.0, "Diastolic_BP": 94.0,
        "Total_Cholesterol": 243.0, "HDL_Cholesterol": 39.0, "Num_Critical_Diseases": 2.0,
        "ICD_E08_E13_Diabetes": 0.0, "ICD_I10_I15_Hypertension": 1.0,
        "ICD_I20_I50_HeartDisease": 1.0, "ICD_J40_J47_Respiratory": 0.0,
        "ICD_N18_KidneyDisease": 0.0, "Smoker": 1.0, "Needs_Walking_Assist": 0.0,
        "Uses_Oxygen": 0.0, "Takes_Diuretics": 1.0, "Takes_Beta_Blockers": 1.0,
        "CVD_Risk_Score": 33.0,
    },
    # سيتي نور حسنة — 62, diabetes + hypertension → Orange (yellow)
    "SA-2024-ID-09887": {
        "Fullname": "Siti Nur Hasanah", "Nationality": "Indonesia", "Gender": "F",
        "Age": 62.0, "BMI": 27.1, "Systolic_BP": 144.0, "Diastolic_BP": 87.0,
        "Total_Cholesterol": 214.0, "HDL_Cholesterol": 49.0, "Num_Critical_Diseases": 2.0,
        "ICD_E08_E13_Diabetes": 1.0, "ICD_I10_I15_Hypertension": 1.0,
        "ICD_I20_I50_HeartDisease": 0.0, "ICD_J40_J47_Respiratory": 0.0,
        "ICD_N18_KidneyDisease": 0.0, "Smoker": 0.0, "Needs_Walking_Assist": 0.0,
        "Uses_Oxygen": 0.0, "Takes_Diuretics": 1.0, "Takes_Beta_Blockers": 0.0,
        "CVD_Risk_Score": 19.0,
    },
}


class Command(BaseCommand):
    help = "Attach triage feature vectors to the demo bracelet pilgrims."

    def handle(self, *args, **options):
        updated = missing = 0
        for patient_id, features in BRACELET_FEATURES.items():
            pilgrim = Pilgrim.objects.filter(patient_id=patient_id).first()
            if pilgrim is None:
                self.stdout.write(self.style.WARNING(f"  no pilgrim {patient_id} — skipped"))
                missing += 1
                continue
            HealthProfile.objects.update_or_create(
                pilgrim=pilgrim,
                defaults={"triage_features": features},
            )
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"Done. updated={updated} missing={missing}")
        )
