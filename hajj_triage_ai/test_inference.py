import pandas as pd
import json
import random
from inference import predict_hajj_triage
from pathlib import Path
import os


# Base Directory 
BASE_DIR = Path(__file__).resolve().parent

print("--- Loading Fake Data ---")
# Load the dataset you generated
df = pd.read_csv(os.path.join(BASE_DIR, "data", "hajj_dataset.csv"))

# Let's find a Red patient to test
red_patients = df[df['Triage_Category'] == 'Red']

# Grab one random row from the Red patients
test_row = red_patients.iloc[random.randint(0, len(red_patients) - 1)]

# Simulate the Payload
# The AI predicts the Triage_Category, so we must drop it from the input data.
# We convert the pandas Series into a clean Python dictionary.
patient_dict = test_row.drop('Triage_Category').to_dict()

print("\nINCOMING PAYLOAD FROM AGENT")
print(json.dumps(patient_dict, indent=2))

# Run the Inference!
print("\nRUNNING XGBOOST INFERENCE")
result = predict_hajj_triage(patient_dict)

# Print the Output exactly as a front-end UI would receive it
print("\nFINAL VIRTUAL HEALTH CARD JSON")
print(json.dumps(result, indent=4))