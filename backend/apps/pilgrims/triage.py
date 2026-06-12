"""Thin bridge from Django to the standalone hajj_triage_ai XGBoost model.

The model code lives outside the Django app (repo_root/hajj_triage_ai), and
importing it loads the model + SHAP explainer (~2s) and pulls in xgboost/shap.
Both are done lazily on first use so normal Django startup and non-triage
requests pay nothing.
"""

import sys

from django.conf import settings

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
