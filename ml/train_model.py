import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
import pickle
import os

def generate_synthetic_data(num_samples=2000):
    np.random.seed(42)
    # distance between 0 and 150 meters
    distance = np.random.uniform(0, 150, num_samples)
    # closing speed between -30 and 60 m/s
    closing_speed = np.random.uniform(-30, 60, num_samples)
    
    # Time to collision (TTC)
    # If closing speed <= 0, TTC is infinity
    ttc = np.where(closing_speed > 0, distance / closing_speed, 999)
    
    # Risk label: 
    # 2 (Critical) if TTC < 2.0s
    # 1 (Warning) if TTC < 5.0s
    # 0 (Safe) otherwise
    risk_label = np.zeros(num_samples)
    risk_label[ttc < 5.0] = 1
    risk_label[ttc < 2.0] = 2
    
    df = pd.DataFrame({
        'distance': distance,
        'closing_speed': closing_speed,
        'risk_label': risk_label
    })
    return df

def train_and_save_model():
    print("Generating synthetic data...")
    df = generate_synthetic_data()
    X = df[['distance', 'closing_speed']]
    y = df['risk_label']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)
    
    score = model.score(X_test, y_test)
    print(f"Model trained with accuracy: {score:.2f}")
    
    os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'collision_risk_model.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train_and_save_model()
