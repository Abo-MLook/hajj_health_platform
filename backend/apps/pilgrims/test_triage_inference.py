
from datetime import date
from django.test import TestCase
from apps.pilgrims.models import Pilgrim, HealthProfile
from apps.pilgrims.triage import run_triage_inference, calculate_bmi

class TriageInferenceTests(TestCase):
    def setUp(self):
        self.pilgrim_healthy = Pilgrim.objects.create(
            full_name="Healthy Pilgrim",
            passport_number="H12345",
            date_of_birth=date(1990, 1, 1),
            gender="male"
        )
        self.profile_healthy = HealthProfile.objects.create(
            pilgrim=self.pilgrim_healthy,
            height=180,
            weight=75,
            systolic_bp=110,
            diastolic_bp=70,
            total_cholesterol=150,
            hdl_cholesterol=60,
            smoker=False,
            uses_oxygen=False,
            needs_walking_assist=False,
            diseases_text="",
            medications_text=""
        )
        
        self.pilgrim_risk = Pilgrim.objects.create(
            full_name="At Risk Pilgrim",
            passport_number="R12345",
            date_of_birth=date(1950, 1, 1), # Older
            gender="male"
        )
        self.profile_risk = HealthProfile.objects.create(
            pilgrim=self.pilgrim_risk,
            height=170,
            weight=100, # High BMI
            systolic_bp=160, # High BP
            diastolic_bp=95,
            total_cholesterol=250, # High cholesterol
            hdl_cholesterol=40,
            smoker=True,
            uses_oxygen=False,
            needs_walking_assist=False,
            diseases_text="Diabetes, Hypertension, Heart Disease",
            medications_text="Beta Blocker, Diuretic"
        )

    def test_calculate_bmi(self):
        self.assertEqual(calculate_bmi(75, 180), 23.1)
        self.assertIsNone(calculate_bmi(None, 180))

    def test_triage_inference_healthy(self):
        run_triage_inference(self.profile_healthy)
        self.profile_healthy.refresh_from_db()
        self.assertIsNotNone(self.profile_healthy.triage_category)
        self.assertIn(self.profile_healthy.triage_category, ["Green", "Orange", "Red"])
        
    def test_triage_inference_risk(self):
        run_triage_inference(self.profile_risk)
        self.profile_risk.refresh_from_db()
        self.assertIsNotNone(self.profile_risk.triage_category)
        # With all those risk factors, they should ideally not be Green
        self.assertNotEqual(self.profile_risk.triage_category, "Green")
