import pandas as pd
import numpy as np
import xgboost as xgb
import shap
from pathlib import Path
import os

# Load model and explainer globally
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

# The Framingham calculator (needs to be applied to the raw CSV)
def calculate_cvd_risk(row):
    points = 0
    if pd.notna(row.get('Age')) and row['Age'] > 40: points += (row['Age'] - 40) // 5
    sys_bp = row.get('Systolic_BP')
    if pd.notna(sys_bp):
        if sys_bp > 130: points += 1
        if sys_bp > 140: points += 1
        if sys_bp > 160: points += 2
    tc = row.get('Total_Cholesterol')
    if pd.notna(tc):
        if tc > 200: points += 1
        if tc > 240: points += 2
    hdl = row.get('HDL_Cholesterol')
    if pd.notna(hdl):
        if hdl < 40: points += 2
        if hdl > 60: points -= 1
    if pd.notna(row.get('Smoker')) and row['Smoker'] == 1: points += 3
    if pd.notna(row.get('ICD_E08_E13_Diabetes')) and row['ICD_E08_E13_Diabetes'] == 1: points += 3
    return round(min(max(points * 2.5, 1.0), 45.0), 1)


def process_batch_csv(input_csv_path, output_csv_path):
    df = pd.read_csv(input_csv_path)
    
    # Calculate CVD Risk if it isn't already in the CSV
    if 'CVD_Risk_Score' not in df.columns:
        df['CVD_Risk_Score'] = df.apply(calculate_cvd_risk, axis=1)

    # Clean the data for the model
    cols_to_drop = ['Fullname', 'Nationality', 'Passport_Number', 'Triage_Category']
    df_model = df.drop(columns=[c for c in cols_to_drop if c in df.columns])
    
    if 'Gender' in df_model.columns:
        # Only map if it's currently strings
        if 'Gender' in df_model.columns and isinstance(df_model['Gender'].iloc[0], str):
            df_model['Gender'] = df_model['Gender'].map({'M': 0, 'F': 1})

    # XGBoost can predict thousands of rows in milliseconds
    predictions = model.predict(df_model)
    
    # Map back to strings for the output CSV
    cat_names = {0: 'Green', 1: 'Orange', 2: 'Red'}
    df['AI_Triage_Category'] = [cat_names[pred] for pred in predictions]

    # We calculate SHAP values for the whole batch
    shap_values = explainer.shap_values(df_model)
    
    reasons_list = []
    
    # Loop through the results to assign reasons
    for idx, pred in enumerate(predictions):
        if pred == 0:
            reasons_list.append("Low Risk")
            continue
            
        # Extract SHAP for this specific patient
        if isinstance(shap_values, list):
            patient_shap = shap_values[pred][idx]
        else:
            patient_shap = shap_values[idx, :, pred]
            
        feature_impacts = list(zip(df_model.columns, patient_shap, df_model.iloc[idx]))
        feature_impacts.sort(key=lambda x: x[1], reverse=True)
        
        patient_reasons = []
        for feature, impact, value in feature_impacts:
            if impact > 0.05:
                if feature in BINARY_FEATURES and value == 0:
                    continue
                
                val_display = "Missing" if pd.isna(value) else value
                if feature in BINARY_FEATURES and value == 1:
                    val_display = "Yes"
                if feature == 'CVD_Risk_Score':
                    val_display = f"{val_display}%"
                    
                patient_reasons.append(f"{feature.replace('_', ' ')}: {val_display}")
        
        if not patient_reasons:
            patient_reasons.append("Elevated combination of baseline vitals")
            
        # Join the top reasons into a single readable string
        reasons_list.append(" | ".join(patient_reasons))

    # Append the reasons to our final dataframe
    df['Primary_Risk_Factors'] = reasons_list

    df.to_csv(output_csv_path, index=False)


if __name__ == "__main__":
    # Test it using your existing fake data
    process_batch_csv('D:/Github_Projects/Hajj_Hackathon/hajj_health_platform/hajj_triage_ai/data/hajj_dataset.csv', 'D:/Github_Projects/Hajj_Hackathon/hajj_health_platform/hajj_triage_ai/data/triaged_hujjaj_output.csv')