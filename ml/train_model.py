"""
V2V-SCADA Prototype Collision Risk Classifier - Model Training Pipeline
========================================================================

NOTICE ON DATASET & PROTOTYPE NATURE:
-------------------------------------
This machine learning component is a PROTOTYPE collision-risk classifier developed
for an academic engineering demonstration.

The default training dataset is SYNTHETICALLY GENERATED using kinematic physics
and deterministic Time-to-Collision (TTC) formulas. It is NOT trained on real-world
automotive fleet or production crash sensor data, and must NOT be characterized as
production automotive autonomous emergency braking (AEB) AI.

The architecture is structured so that real vehicular telemetry datasets (e.g.,
NGSIM, HighD, or CAN bus/GNSS logs) can replace the synthetic generator by providing
a CSV file to `load_dataset()`.

TTC-based Class Definitions:
- Class 0 (Safe): TTC >= 5.0 seconds or negative closing speed (diverging/parallel)
- Class 1 (Warning): 2.0s <= TTC < 5.0s
- Class 2 (Critical): TTC < 2.0s (requires immediate braking advisory)
"""

import os
import json
import pickle
import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)

# Deterministic random seed for reproducibility
RANDOM_SEED = 42

MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(MODEL_DIR, "collision_risk_model.pkl")
METRICS_FILE = os.path.join(MODEL_DIR, "model_metrics.json")


def generate_synthetic_dataset(num_samples: int = 5000, random_seed: int = RANDOM_SEED) -> pd.DataFrame:
    """
    Generates synthetic 2D relative motion kinematic samples.
    
    Features:
    - distance: Relative distance between vehicles in meters [0.5, 200.0]
    - closing_speed: Relative approach rate in m/s [-30.0, 60.0]
      (Negative implies vehicles are diverging; positive implies closing distance)
      
    Target Label:
    - 0: Safe (TTC >= 5.0s or diverging)
    - 1: Warning (2.0s <= TTC < 5.0s)
    - 2: Critical (TTC < 2.0s)
    """
    rng = np.random.default_rng(random_seed)
    
    # Distance between 0.5m and 180m
    distance = rng.uniform(0.5, 180.0, num_samples)
    
    # Relative closing speed between -30 m/s (separating) and +55 m/s (rapidly approaching)
    closing_speed = rng.uniform(-30.0, 55.0, num_samples)
    
    # Calculate kinematic Time-to-Collision (TTC) in seconds
    # If closing_speed <= 0, vehicles are separating or parallel -> TTC is infinite
    ttc = np.where(closing_speed > 0.1, distance / closing_speed, 999.0)
    
    # Assign ground truth risk labels based on standard ISO 15623 / Euro-NCAP TTC thresholds
    risk_label = np.zeros(num_samples, dtype=int)
    risk_label[(ttc < 5.0) & (ttc >= 2.0)] = 1
    risk_label[ttc < 2.0] = 2
    
    df = pd.DataFrame({
        "distance": np.round(distance, 2),
        "closing_speed": np.round(closing_speed, 2),
        "risk_label": risk_label
    })
    
    return df


def evaluate_model(
    model: LogisticRegression,
    X_test: pd.DataFrame,
    y_test: pd.Series
) -> Dict[str, Any]:
    """
    Computes standard multi-class classification evaluation metrics.
    """
    y_pred = model.predict(X_test)
    
    acc = float(accuracy_score(y_test, y_pred))
    prec_weighted = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
    rec_weighted = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))
    f1_weighted = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
    
    cm = confusion_matrix(y_test, y_pred).tolist()
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    
    metrics = {
        "prototype_note": "Trained on synthetic kinematic dataset derived from TTC formulas.",
        "random_seed": RANDOM_SEED,
        "test_samples": int(len(y_test)),
        "accuracy": round(acc, 4),
        "precision_weighted": round(prec_weighted, 4),
        "recall_weighted": round(rec_weighted, 4),
        "f1_score_weighted": round(f1_weighted, 4),
        "confusion_matrix": cm,
        "class_report": report
    }
    
    return metrics


def train_and_save_model(csv_path: str = None) -> Tuple[LogisticRegression, Dict[str, Any]]:
    """
    Trains the Logistic Regression risk classifier and persists the model and metrics.
    If csv_path is provided, loads real telemetry data; otherwise generates synthetic data.
    """
    if csv_path and os.path.exists(csv_path):
        print(f"[ML Pipeline] Loading telemetry dataset from: {csv_path}")
        df = pd.read_csv(csv_path)
    else:
        print(f"[ML Pipeline] Generating {5000} synthetic kinematic training samples (seed={RANDOM_SEED})...")
        df = generate_synthetic_dataset(num_samples=5000, random_seed=RANDOM_SEED)
        
    X = df[["distance", "closing_speed"]]
    y = df["risk_label"]
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )
    
    print("[ML Pipeline] Fitting LogisticRegression classifier...")
    model = LogisticRegression(
        max_iter=1000,
        random_state=RANDOM_SEED,
        class_weight="balanced"
    )
    model.fit(X_train, y_train)
    
    metrics = evaluate_model(model, X_test, y_test)
    print(f"[ML Pipeline] Test Accuracy:  {metrics['accuracy'] * 100:.2f}%")
    print(f"[ML Pipeline] F1-Score (W):  {metrics['f1_score_weighted']:.4f}")
    print(f"[ML Pipeline] Confusion Matrix: {metrics['confusion_matrix']}")
    
    # Save Model Artifact
    with open(MODEL_FILE, "wb") as f:
        pickle.dump(model, f)
    print(f"[ML Pipeline] Model saved: {MODEL_FILE}")
    
    # Save Metrics Artifact
    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"[ML Pipeline] Metrics saved: {METRICS_FILE}")
    
    return model, metrics


if __name__ == "__main__":
    train_and_save_model()
