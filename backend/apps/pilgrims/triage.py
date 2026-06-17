"""Bridge from Django to the standalone hajj_triage_ai XGBoost model.

The model code lives outside the Django app (repo_root/hajj_triage_ai), and
importing it loads the model + SHAP explainer (~2s) and pulls in xgboost/shap.
Both are done lazily on first use so normal Django startup and non-triage
requests pay nothing.

Two entry points:

- ``run_triage(features)`` — thin: run the model on a prebuilt feature vector.
  Used by the API when a profile already has ``triage_features`` stored.
- ``run_triage_inference(profile)`` — fat: derive metrics (BMI, CVD), map the
  free-text profile to a feature vector, persist it, run the model, and write
  the result back onto the HealthProfile. Used by the extraction pipeline.
"""

import logging
import sys

from django.conf import settings

logger = logging.getLogger(__name__)

# repo_root/hajj_triage_ai — sibling of the Django backend dir.
_TRIAGE_DIR = settings.BASE_DIR.parent / "hajj_triage_ai"

_predict = None  # cached predict_hajj_triage callable

# Model status (Green/Orange/Red) → the clients' RiskLevel (green/yellow/red).
RISK_LEVEL = {"Green": "green", "Orange": "yellow", "Red": "red"}


def _load():
    """Import predict_hajj_triage once, adding hajj_triage_ai to sys.path."""
    global _predict
    if _predict is None:
        path = str(_TRIAGE_DIR)
        if path not in sys.path:
            sys.path.insert(0, path)
        from inference import predict_hajj_triage  # heavy: loads model + explainer

        _predict = predict_hajj_triage
    return _predict


def run_triage(features: dict) -> dict:
    """Run the triage model on a stored feature vector and return the model's
    payload augmented with a normalized `risk_level`. Raises on bad input —
    callers handle that and report insufficient/failed triage."""
    predict = _load()
    result = predict(features)
    result["risk_level"] = RISK_LEVEL.get(result.get("status"), None)
    return result


def calculate_bmi(weight_kg, height_cm):
    if not weight_kg or not height_cm:
        return None
    try:
        height_m = float(height_cm) / 100.0
        if height_m <= 0:
            return None
        return round(float(weight_kg) / (height_m * height_m), 1)
    except (TypeError, ValueError):
        return None


def calculate_cvd_risk_score(profile):
    """Approximate CVD risk from age, BP, cholesterol and smoking.
    A real system would use a validated formula (e.g., Framingham)."""
    if not profile.pilgrim.age or not profile.systolic_bp or not profile.total_cholesterol:
        return None
    try:
        score = 0
        if profile.pilgrim.age > 50:
            score += 10
        if profile.pilgrim.age > 60:
            score += 10
        if profile.systolic_bp > 130:
            score += 15
        if profile.systolic_bp > 140:
            score += 15
        if profile.total_cholesterol > 200:
            score += 10
        if profile.smoker:
            score += 20
        return min(round(score, 1), 100.0)
    except (TypeError, ValueError):
        return None


def build_feature_vector(profile):
    """Map a HealthProfile's structured + free-text fields to the exact dict
    shape predict_hajj_triage expects (see import_triage_csv NUMERIC_FEATURES).
    Returns ``(bmi, cvd_risk, features)``."""
    bmi = calculate_bmi(profile.weight, profile.height)
    cvd_risk = calculate_cvd_risk_score(profile)

    diseases_lower = (profile.diseases_text or "").lower()
    medications_lower = (profile.medications_text or "").lower()

    diabetes = 1 if "diabetes" in diseases_lower else 0
    hypertension = 1 if "hypertension" in diseases_lower else 0
    heart_disease = 1 if any(w in diseases_lower for w in ["heart", "cardiac", "myocardial", "coronary"]) else 0
    respiratory = 1 if any(w in diseases_lower for w in ["asthma", "copd", "respiratory", "bronchitis"]) else 0
    kidney_disease = 1 if any(w in diseases_lower for w in ["kidney", "renal", "nephro"]) else 0

    num_critical_diseases = diabetes + hypertension + heart_disease + respiratory + kidney_disease

    return bmi, cvd_risk, {
        "Gender": "M" if profile.pilgrim.gender == "male" else ("F" if profile.pilgrim.gender == "female" else None),
        "Age": profile.pilgrim.age,
        "BMI": bmi,
        "Systolic_BP": profile.systolic_bp,
        "Diastolic_BP": profile.diastolic_bp,
        "Total_Cholesterol": profile.total_cholesterol,
        "HDL_Cholesterol": profile.hdl_cholesterol,
        "Num_Critical_Diseases": num_critical_diseases,
        "ICD_E08_E13_Diabetes": diabetes,
        "ICD_I10_I15_Hypertension": hypertension,
        "ICD_I20_I50_HeartDisease": heart_disease,
        "ICD_J40_J47_Respiratory": respiratory,
        "ICD_N18_KidneyDisease": kidney_disease,
        "Smoker": 1 if profile.smoker else 0,
        "Needs_Walking_Assist": 1 if profile.needs_walking_assist else 0,
        "Uses_Oxygen": 1 if profile.uses_oxygen else 0,
        "Takes_Diuretics": 1 if "diuretic" in medications_lower else 0,
        "Takes_Beta_Blockers": 1 if ("beta blocker" in medications_lower or "olol" in medications_lower) else 0,
        "CVD_Risk_Score": cvd_risk,
    }


def run_triage_inference(profile):
    """Derive metrics, build + persist the feature vector, run the model, and
    write the result back onto the HealthProfile. Best-effort: logs and returns
    on failure so the extraction pipeline isn't broken by a triage error."""
    try:
        bmi, cvd_risk, features = build_feature_vector(profile)
        profile.bmi = bmi
        profile.cvd_risk_score = cvd_risk
        profile.triage_features = features

        result = run_triage(features)
        profile.triage_category = result.get("status")
        profile.triage_reasoning = result

        profile.save(update_fields=[
            "bmi", "cvd_risk_score", "triage_features",
            "triage_category", "triage_reasoning", "updated_at",
        ])
        logger.info("Triage inference successful for profile %s: %s", profile.pk, profile.triage_category)
    except Exception:
        logger.exception("Failed to run triage inference for profile %s", profile.pk)
