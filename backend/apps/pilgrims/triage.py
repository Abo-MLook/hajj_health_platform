import sys
import os
import logging
from django.conf import settings

# Ensure we can import from hajj_triage_ai
# backend/apps/pilgrims/triage.py -> backend/apps/pilgrims -> backend/apps -> backend -> hajj_health_platform
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from hajj_triage_ai.inference import predict_hajj_triage

logger = logging.getLogger(__name__)

def calculate_bmi(weight_kg, height_cm):
    if not weight_kg or not height_cm:
        return None
    try:
        height_m = float(height_cm) / 100.0
        if height_m <= 0:
            return None
        return round(float(weight_kg) / (height_m * height_m), 1)
    except Exception:
        return None

def calculate_cvd_risk_score(profile):
    """
    Dummy CVD risk calculation based on age, bp, cholesterol and smoking.
    A real system would use a validated formula (e.g., Framingham).
    """
    if not profile.pilgrim.age or not profile.systolic_bp or not profile.total_cholesterol:
        return None
    
    try:
        score = 0
        if profile.pilgrim.age > 50: score += 10
        if profile.pilgrim.age > 60: score += 10
        
        if profile.systolic_bp > 130: score += 15
        if profile.systolic_bp > 140: score += 15
        
        if profile.total_cholesterol > 200: score += 10
        
        if profile.smoker: score += 20
        
        return min(round(score, 1), 100.0)
    except Exception:
        return None

def run_triage_inference(profile):
    """
    Calculates derived metrics (BMI, CVD), maps text to ML features,
    runs the AI inference, and updates the HealthProfile.
    """
    try:
        # Calculate derived metrics
        bmi = calculate_bmi(profile.weight, profile.height)
        cvd_risk = calculate_cvd_risk_score(profile)
        
        profile.bmi = bmi
        profile.cvd_risk_score = cvd_risk
        
        # Prepare dictionary for inference
        diseases_lower = (profile.diseases_text or "").lower()
        medications_lower = (profile.medications_text or "").lower()
        
        diabetes = 1 if 'diabetes' in diseases_lower else 0
        hypertension = 1 if 'hypertension' in diseases_lower else 0
        heart_disease = 1 if any(word in diseases_lower for word in ['heart', 'cardiac', 'myocardial', 'coronary']) else 0
        respiratory = 1 if any(word in diseases_lower for word in ['asthma', 'copd', 'respiratory', 'bronchitis']) else 0
        kidney_disease = 1 if any(word in diseases_lower for word in ['kidney', 'renal', 'nephro']) else 0
        
        num_critical_diseases = diabetes + hypertension + heart_disease + respiratory + kidney_disease

        patient_data_dict = {
            'Gender': 'M' if profile.pilgrim.gender == 'male' else ('F' if profile.pilgrim.gender == 'female' else None),
            'Age': profile.pilgrim.age,
            'BMI': bmi,
            'Systolic_BP': profile.systolic_bp,
            'Diastolic_BP': profile.diastolic_bp,
            'Total_Cholesterol': profile.total_cholesterol,
            'HDL_Cholesterol': profile.hdl_cholesterol,
            'Num_Critical_Diseases': num_critical_diseases,
            'ICD_E08_E13_Diabetes': diabetes,
            'ICD_I10_I15_Hypertension': hypertension,
            'ICD_I20_I50_HeartDisease': heart_disease,
            'ICD_J40_J47_Respiratory': respiratory,
            'ICD_N18_KidneyDisease': kidney_disease,
            'Smoker': 1 if profile.smoker else 0,
            'Needs_Walking_Assist': 1 if profile.needs_walking_assist else 0,
            'Uses_Oxygen': 1 if profile.uses_oxygen else 0,
            'Takes_Diuretics': 1 if 'diuretic' in medications_lower else 0,
            'Takes_Beta_Blockers': 1 if 'beta blocker' in medications_lower or 'olol' in medications_lower else 0,
            'CVD_Risk_Score': cvd_risk,
        }
        
        result = predict_hajj_triage(patient_data_dict)
        
        profile.triage_category = result.get("status")
        profile.triage_reasoning = result
        
        profile.save(update_fields=["bmi", "cvd_risk_score", "triage_category", "triage_reasoning", "updated_at"])
        logger.info("Triage inference successful for profile %s: %s", profile.pk, profile.triage_category)
        
    except Exception as e:
        logger.exception("Failed to run triage inference for profile %s", profile.pk)
