import os
import pandas as pd
import numpy as np
import random
from faker import Faker
from pathlib import Path

# Generates simulated fake data of Hujjaj based on different perposions of age groups

def generate_synthetic_hajj_data(num_records=1000):
    
    fake = Faker()

    # We weight the probabilities to make the data realistic for Hajj (e.g., older demographic)
    age_groups = np.random.choice(['18-30', '31-50', '51-65', '66-80', '80+'], num_records, p=[0.1, 0.3, 0.4, 0.15, 0.05])
    
    data = []
    for i in range(num_records):
        group = age_groups[i]
        if group == '18-30': age = random.randint(18, 30)
        elif group == '31-50': age = random.randint(31, 50)
        elif group == '51-65': age = random.randint(51, 65)
        elif group == '66-80': age = random.randint(66, 80)
        else: age = random.randint(81, 95)
        
        height_cm = random.randint(150, 190)
        weight_kg = random.randint(50, 120)
        bmi = round(weight_kg / ((height_cm / 100) ** 2), 1)
        
        # Blood Pressure Generation (Linked slightly to age/weight for realism)
        if age > 50 or bmi > 30:
            systolic_bp = random.randint(120, 160) 
            diastolic_bp = random.randint(80, 95)
        else:
            systolic_bp = random.randint(100, 130)
            diastolic_bp = random.randint(65, 85)

        # Add a tiny chance (2%) for a dangerous BP spike for our Red cases
        if random.random() < 0.02: systolic_bp = random.randint(170, 195)

        total_cholesterol = random.randint(150, 280) if age > 40 else random.randint(130, 220)
        hdl_cholesterol = random.randint(30, 75)
        prob_mod = 0.3 if age > 60 else 0.05
        
        icd_hypertension = 1 if systolic_bp >= 140 else np.random.choice([0, 1], p=[0.85, 0.15])
        icd_diabetes = np.random.choice([0, 1], p=[1-prob_mod, prob_mod])
        icd_heart = np.random.choice([0, 1], p=[1-(prob_mod/3), prob_mod/3])
        icd_kidney = np.random.choice([0, 1], p=[0.95, 0.05])
        icd_respiratory = np.random.choice([0, 1], p=[0.98, 0.02])
        
        smoker = np.random.choice([0, 1], p=[0.8, 0.2])
        needs_walking_assist = np.random.choice([0, 1], p=[0.95, 0.05]) if age > 65 else 0
        uses_oxygen = np.random.choice([0, 1], p=[0.99, 0.01]) if age > 70 else 0
        takes_diuretics = 1 if (icd_hypertension == 1 or icd_heart == 1) and random.random() > 0.5 else 0
        takes_beta_blockers = 1 if icd_heart == 1 and random.random() > 0.3 else 0
        
        num_critical_diseases = icd_diabetes + icd_hypertension + icd_heart + icd_kidney + icd_respiratory

        record = {
            'Fullname': fake.name(),
            'Nationality': fake.country(),
            'Gender': random.choice(['M', 'F']),
            'Passport_Number': fake.ean13(),

            'Age': age,
            'BMI': bmi,
            'Systolic_BP': systolic_bp,
            'Diastolic_BP': diastolic_bp,
            'Total_Cholesterol': total_cholesterol,
            'HDL_Cholesterol': hdl_cholesterol,
            'Num_Critical_Diseases': num_critical_diseases,

            'ICD_E08_E13_Diabetes': icd_diabetes,
            'ICD_I10_I15_Hypertension': icd_hypertension,
            'ICD_I20_I50_HeartDisease': icd_heart,
            'ICD_J40_J47_Respiratory': icd_respiratory,
            'ICD_N18_KidneyDisease': icd_kidney,

            'Smoker': smoker,
            'Needs_Walking_Assist': needs_walking_assist,
            'Uses_Oxygen': uses_oxygen,
            'Takes_Diuretics': takes_diuretics,
            'Takes_Beta_Blockers': takes_beta_blockers
        }
        data.append(record)
    
    return pd.DataFrame(data)

def calculate_cvd_risk(row):
    points = 0
    
    # Safely check age
    if pd.notna(row.get('Age')) and row['Age'] > 40: 
        points += (row['Age'] - 40) // 5
        
    # Safely check BP
    sys_bp = row.get('Systolic_BP')
    if pd.notna(sys_bp):
        if sys_bp > 130: points += 1
        if sys_bp > 140: points += 1
        if sys_bp > 160: points += 2
        
    # Safely check Cholesterol
    tc = row.get('Total_Cholesterol')
    if pd.notna(tc):
        if tc > 200: points += 1
        if tc > 240: points += 2
        
    hdl = row.get('HDL_Cholesterol')
    if pd.notna(hdl):
        if hdl < 40: points += 2
        if hdl > 60: points -= 1
        
    # Safely check binary conditions
    if pd.notna(row.get('Smoker')) and row['Smoker'] == 1: points += 3
    if pd.notna(row.get('ICD_E08_E13_Diabetes')) and row['ICD_E08_E13_Diabetes'] == 1: points += 3
        
    return round(min(max(points * 2.5, 1.0), 45.0), 1)

def classify_hajji(row):
    if row['Uses_Oxygen'] == 1: return 'Red'
    if row['Systolic_BP'] >= 180 or row['Diastolic_BP'] >= 110: return 'Red'
    if row['CVD_Risk_Score'] > 20.0 and row['Age'] >= 60: return 'Red'
    
    # ORANGE FLAGS (Require a combination of risks, or specific heat-threat meds)
    if row['Takes_Diuretics'] == 1 or row['Takes_Beta_Blockers'] == 1: return 'Orange'
    if row['Needs_Walking_Assist'] == 1: return 'Orange'
    if row['CVD_Risk_Score'] >= 15.0: return 'Orange'
    if (row['Systolic_BP'] >= 150) and (row['Num_Critical_Diseases'] >= 1): return 'Orange'
    if row['BMI'] >= 35 and row['Age'] > 50: return 'Orange'
    if row['Num_Critical_Diseases'] >= 2: return 'Orange'
    
    return 'Green'

if __name__ == "__main__":
    # Directory containing generate_data.py
    BASE_DIR = Path(__file__).resolve().parent

    # hajj_triage_ai/data
    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(exist_ok=True)
    df = generate_synthetic_hajj_data(1000)
    df['CVD_Risk_Score'] = df.apply(calculate_cvd_risk, axis=1)
    df['Triage_Category'] = df.apply(classify_hajji, axis=1)
    df.to_csv(DATA_DIR / "hajj_dataset.csv", index=False)