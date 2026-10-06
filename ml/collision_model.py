"""
V2V-SCADA Prototype Collision Risk Predictor
============================================

Provides an inference wrapper for the trained prototype collision-risk model.
Includes deterministic rule-based TTC fallback if the model file is absent or corrupted.

NOTICE:
This is an academic prototype classifier trained on synthetic kinematic TTC data.
It should not be used as a production automotive safety-critical decision system.
"""

import os
import pickle
import logging
import pandas as pd
from typing import Optional

logger = logging.getLogger("v2v_collision_predictor")
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "collision_risk_model.pkl")


class CollisionPredictor:
    """
    Collision risk predictor with resilient fallback.
    Returns:
        0: Safe
        1: Warning
        2: Critical
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or MODEL_PATH
        self.model = None
        self._load_error: Optional[str] = None
        self.load_model()

    def load_model(self) -> bool:
        """
        Safely attempts to load the pickled model file.
        Returns True if loaded, False if fallback should be used.
        """
        if not os.path.exists(self.model_path):
            self._load_error = f"Model artifact not found at {self.model_path}"
            logger.warning(f"[CollisionPredictor] {self._load_error}. Using rule-based fallback.")
            self.model = None
            return False

        try:
            with open(self.model_path, "rb") as f:
                loaded = pickle.load(f)
                # Basic sanity check that loaded object has a predict method
                if not hasattr(loaded, "predict"):
                    raise ValueError("Loaded object does not implement a predict() method.")
                self.model = loaded
                self._load_error = None
                logger.info("[CollisionPredictor] Collision risk classifier loaded successfully.")
                return True
        except Exception as exc:
            self._load_error = str(exc)
            logger.error(f"[CollisionPredictor] Failed to deserialize model: {exc}. Using rule-based fallback.")
            self.model = None
            return False

    def is_loaded(self) -> bool:
        """Returns True if the ML model is currently active and loaded."""
        return self.model is not None

    def predict_risk(self, distance: float, closing_speed: float) -> int:
        """
        Predicts collision risk given distance (m) and closing speed (m/s).
        
        Args:
            distance: Physical separation in meters (must be >= 0.0)
            closing_speed: Relative approach rate in m/s (positive = approaching, negative = separating)
            
        Returns:
            0: Safe (No imminent threat)
            1: Warning (Advisory alert)
            2: Critical (Braking intervention recommended)
        """
        # Guard against invalid negative distances
        dist = max(0.0, float(distance))
        cs = float(closing_speed)

        # Fallback to deterministic rule-based TTC physics if ML model is unavailable
        if self.model is None:
            return self._rule_based_fallback(dist, cs)

        try:
            # Construct DataFrame with explicit column names to prevent scikit-learn feature name warnings
            features = pd.DataFrame(
                [[dist, cs]],
                columns=["distance", "closing_speed"]
            )
            prediction = self.model.predict(features)
            return int(prediction[0])
        except Exception as exc:
            logger.warning(f"[CollisionPredictor] Inference error ({exc}). Falling back to rule-based logic.")
            return self._rule_based_fallback(dist, cs)

    @staticmethod
    def _rule_based_fallback(distance: float, closing_speed: float) -> int:
        """
        Standard ISO 15623 Time-to-Collision (TTC) heuristic:
        - If closing_speed <= 0.1 m/s: vehicles are separating or stationary -> Safe (0)
        - If TTC < 2.0s: Critical (2)
        - If TTC < 5.0s: Warning (1)
        - Otherwise: Safe (0)
        """
        if closing_speed <= 0.1:
            return 0
        ttc = distance / closing_speed
        if ttc < 2.0:
            return 2
        if ttc < 5.0:
            return 1
        return 0
