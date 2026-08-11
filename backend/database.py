import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'v2v_data.db')

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table for raw telemetry
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id TEXT,
        timestamp INTEGER,
        lat REAL,
        lon REAL,
        speed_kmph REAL,
        heading_deg REAL,
        raw_payload TEXT,
        received_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Table for alarms/incidents
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_a TEXT,
        vehicle_b TEXT,
        distance REAL,
        closing_speed REAL,
        risk_level INTEGER,
        incident_time DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def log_telemetry(payload):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO telemetry (vehicle_id, timestamp, lat, lon, speed_kmph, heading_deg, raw_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        payload.get('vehicle_id'),
        payload.get('timestamp'),
        payload.get('lat'),
        payload.get('lon'),
        payload.get('speed_kmph'),
        payload.get('heading_deg'),
        json.dumps(payload)
    ))
    conn.commit()
    conn.close()

def log_incident(v_a, v_b, distance, closing_speed, risk_level):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO incidents (vehicle_a, vehicle_b, distance, closing_speed, risk_level)
        VALUES (?, ?, ?, ?, ?)
    ''', (v_a, v_b, distance, closing_speed, risk_level))
    conn.commit()
    conn.close()

def get_recent_incidents(limit=50):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM incidents ORDER BY id DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows
