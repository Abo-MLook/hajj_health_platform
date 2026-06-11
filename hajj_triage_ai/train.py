import os
from pathlib import Path
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split

# Directory containing train.py
BASE_DIR = Path(__file__).resolve().parent

# hajj_triage_ai/models
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

def train_and_save_model():
    df = pd.read_csv(os.path.join(BASE_DIR, "data", "hajj_dataset.csv"))
    
    X = df.drop(columns=['Fullname', 'Nationality', 'Passport_Number', 'Triage_Category'])
    X['Gender'] = X['Gender'].map({'M': 0, 'F': 1})
    
    target_mapping = {'Green': 0, 'Orange': 1, 'Red': 2}
    y = df['Triage_Category'].map(target_mapping)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = xgb.XGBClassifier(
        objective='multi:softmax', 
        num_class=3, 
        max_depth=4, 
        learning_rate=0.1,
        random_state=42
    )
    model.fit(X_train, y_train)
    
    model.save_model(os.path.join(MODELS_DIR, 'xgboost_triage_model.json'))

if __name__ == "__main__":
    train_and_save_model()