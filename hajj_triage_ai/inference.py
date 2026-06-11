import pandas as pd
import numpy as np
import xgboost as xgb
import shap
from pathlib import Path
import os


# Directory containing train.py
BASE_DIR = Path(__file__).resolve().parent

# hajj_triage_ai/models
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Load model globally so it only initializes once
model = xgb.XGBClassifier()
model.load_model(os.path.join(MODELS_DIR, 'xgboost_triage_model.json'))
explainer = shap.TreeExplainer(model)



BINARY_FEATURES = [
    'ICD_E08_E13_Diabetes', 'ICD_I10_I15_Hypertension', 'ICD_I20_I50_HeartDisease', 
    'ICD_J40_J47_Respiratory', 'ICD_N18_KidneyDisease', 'Smoker', 
    'Needs_Walking_Assist', 'Uses_Oxygen', 'Takes_Diuretics', 'Takes_Beta_Blockers'
]

ICD_MAPPING = {
    'ICD_E08_E13_Diabetes': 'Diabetes Mellitus (E08-E13)',
    'ICD_I10_I15_Hypertension': 'Hypertension (I10-I15)',
    'ICD_I20_I50_HeartDisease': 'Heart Disease (I20-I50)',
    'ICD_J40_J47_Respiratory': 'Chronic Respiratory (J40-J47)',
    'ICD_N18_KidneyDisease': 'Chronic Kidney Disease (N18)'
}

def predict_hajj_triage(patient_data_dict):
    """
    Takes a dictionary of patient data, predicts the triage category,
    and returns a structured payload for the Virtual Health Card UI.
    """
    # Convert dict to DataFrame row
    df_patient = pd.DataFrame([patient_data_dict])

    # Drop text metadata before feeding to XGBoost/SHAP
    cols_to_drop = ['Fullname', 'Nationality', 'Passport_Number', 'Triage_Category']
    df_model = df_patient.drop(columns=[c for c in cols_to_drop if c in df_patient.columns])
    
    # Ensure Gender is mapped correctly for the model
    if 'Gender' in df_model.columns and isinstance(df_model['Gender'].iloc[0], str):
        df_model['Gender'] = df_model['Gender'].map({'M': 0, 'F': 1})
        
    predicted_class = model.predict(df_model)[0]
    cat_names = {0: 'Green', 1: 'Orange', 2: 'Red'}
    category_str = cat_names[predicted_class]
    
    # Compile Vitals & Profile
    active_conditions = [name for col, name in ICD_MAPPING.items() if df_patient[col].iloc[0] == 1]
    
    active_meds = []
    if df_patient['Takes_Diuretics'].iloc[0] == 1: active_meds.append("Diuretics")
    if df_patient['Takes_Beta_Blockers'].iloc[0] == 1: active_meds.append("Beta-Blockers")
    if df_patient['Uses_Oxygen'].iloc[0] == 1: active_meds.append("Oxygen Device")
    if df_patient['Needs_Walking_Assist'].iloc[0] == 1: active_meds.append("Walking Assist")

    # Extract SHAP Reasons (if not Green)
    risk_factors = []
    if predicted_class != 0:
        shap_values = explainer.shap_values(df_model)
        
        if isinstance(shap_values, list):
            patient_shap = shap_values[predicted_class][0]
        else:
            patient_shap = shap_values[0, :, predicted_class]
            
        feature_impacts = list(zip(df_model.columns, patient_shap, df_model.iloc[0]))
        feature_impacts.sort(key=lambda x: x[1], reverse=True)
        
        for feature, impact, value in feature_impacts:
            if impact > 0.05:
                if feature in BINARY_FEATURES and value == 0:
                    continue
                
                val_display = "Data Missing" if pd.isna(value) else value
                if feature in BINARY_FEATURES and value == 1:
                    val_display = "Yes"
                if feature == 'CVD_Risk_Score':
                    val_display = f"{val_display}%"
                    
                risk_factors.append({'feature': feature.replace('_', ' '), 'value': val_display})
        
        if not risk_factors:
            risk_factors.append({'feature': 'Baseline Vitals', 'value': 'Elevated combination'})

    # format vitals for the UI
    sys_bp = df_patient['Systolic_BP'].iloc[0]
    dia_bp = df_patient['Diastolic_BP'].iloc[0]
    bp_display = "Data Missing" if pd.isna(sys_bp) or pd.isna(dia_bp) else f"{int(sys_bp)}/{int(dia_bp)}"
    
    tc = df_patient['Total_Cholesterol'].iloc[0]
    hdl = df_patient['HDL_Cholesterol'].iloc[0]
    chol_display = "Data Missing" if pd.isna(tc) or pd.isna(hdl) else f"TC {int(tc)} | HDL {int(hdl)}"

    cvd_risk = df_patient['CVD_Risk_Score'].iloc[0]
    cvd_display = "Data Missing" if pd.isna(cvd_risk) else f"{cvd_risk}%"

    # Construct the structured output JSON/Dictionary
    return {
        "status": category_str,
        "vitals": {
            "CVD_Risk_Percentage": cvd_display,
            "Age": None if pd.isna(df_patient['Age'].iloc[0]) else float(df_patient['Age'].iloc[0]),
            "BMI": None if pd.isna(df_patient['BMI'].iloc[0]) else float(df_patient['BMI'].iloc[0]),
            "Blood_Pressure": bp_display,
            "Cholesterol": chol_display
        },
        "known_conditions": active_conditions,
        "active_support": active_meds,
        "primary_risk_factors": risk_factors
    }


