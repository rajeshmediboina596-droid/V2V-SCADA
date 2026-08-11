import pickle
import os
import numpy as np

# Load the trained model
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'collision_risk_model.pkl')

class CollisionPredictor:
    def __init__(self):
        self.model = None
        self.load_model()

    def load_model(self):
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, 'rb') as f:
                self.model = pickle.load(f)
        else:
            print(f"Warning: Model not found at {MODEL_PATH}. Run train_model.py first.")

    def predict_risk(self, distance, closing_speed):
        """
        Predicts collision risk based on relative distance (m) and closing speed (m/s).
        Returns risk level: 0 (Safe), 1 (Warning), 2 (Critical)
        """
        if self.model is None:
            # Fallback to simple rule-based if model isn't loaded
            ttc = distance / closing_speed if closing_speed > 0 else 999
            if ttc < 2.0: return 2
            if ttc < 5.0: return 1
            return 0
            
        features = np.array([[distance, closing_speed]])
        prediction = self.model.predict(features)
        return int(prediction[0])
