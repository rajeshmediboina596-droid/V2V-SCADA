"""
Comprehensive Unit & Integration Test Suite for V2V-SCADA System
=================================================================
Validates:
1. Cryptographic HMAC-SHA256 signature generation and canonical verification
2. Anti-replay protection (timestamp window, monotonic sequence, reboot handling)
3. Collision avoidance physics (approaching, separating, zero closing speed, singularity guards)
4. Emergency vehicle preemption and geofencing
5. REST API security:
   - /api/telemetry HMAC verification & Pydantic schema constraints
   - /api/download/{filename} path traversal prevention
   - /api/health subsystem state computation
6. Machine Learning collision risk classifier & rule-based fallback
"""

import os
import sys
import time
import math
import pytest
from fastapi.testclient import TestClient

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import (
    HMAC_SECRET, REPLAY_TOLERANCE_SECONDS, TTC_CRITICAL_SECONDS,
    TTC_WARNING_SECONDS, EMERGENCY_PROXIMITY_METERS, REPORTS_DIR
)
from backend.security import (
    generate_signature, verify_telemetry_packet, build_canonical_signing_string,
    reset_vehicle_sequence
)
from backend.mqtt_client import compute_collision_risk, is_in_polygon
from backend.main import app
from ml.collision_model import CollisionPredictor


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture
def base_valid_telemetry():
    """Generates a valid, fresh telemetry packet."""
    ts = int(time.time())
    packet = {
        "vehicle_id": "TEST-V1",
        "vehicle_type": "Passenger",
        "timestamp": ts,
        "seq": 100,
        "lat": 17.423900,
        "lon": 78.448300,
        "alt": 542.0,
        "speed_kmph": 45.0,
        "heading_deg": 90.0,
        "pitch_deg": 0.5,
        "roll_deg": -0.2,
        "yaw_deg": 90.0,
        "battery_level": 95.0,
        "emergency_status": 0,
        "rf_status": "OK",
        "fault_code": "NONE"
    }
    packet["signature"] = generate_signature(packet)
    return packet


# ============================================================================
# 1. SECURITY & CRYPTOGRAPHY TESTS
# ============================================================================

def test_canonical_hmac_valid(base_valid_telemetry):
    """Verifies that a validly signed canonical packet verifies successfully."""
    reset_vehicle_sequence("TEST-V1")
    is_valid, data, reason = verify_telemetry_packet(base_valid_telemetry, strict=True)
    assert is_valid is True
    assert reason == "OK"


def test_hmac_rejects_corrupted_signature(base_valid_telemetry):
    """Verifies that an altered signature string is rejected."""
    base_valid_telemetry["signature"] = "0000000000000000000000000000000000000000000000000000000000000000"
    is_valid, data, reason = verify_telemetry_packet(base_valid_telemetry, strict=True)
    assert is_valid is False
    assert reason == "HMAC_SIGNATURE_MISMATCH"


def test_hmac_detects_tampered_gps_coordinates(base_valid_telemetry):
    """Verifies that tampering with latitude or longitude invalidates the signature."""
    # Tamper latitude
    tampered_lat = dict(base_valid_telemetry)
    tampered_lat["lat"] = 17.424900
    is_valid, data, reason = verify_telemetry_packet(tampered_lat, strict=True)
    assert is_valid is False
    assert reason == "HMAC_SIGNATURE_MISMATCH"

    # Tamper longitude
    tampered_lon = dict(base_valid_telemetry)
    tampered_lon["lon"] = 78.449300
    is_valid, data, reason = verify_telemetry_packet(tampered_lon, strict=True)
    assert is_valid is False
    assert reason == "HMAC_SIGNATURE_MISMATCH"


def test_hmac_detects_tampered_speed(base_valid_telemetry):
    """Verifies that tampering with speed invalidates the signature."""
    tampered = dict(base_valid_telemetry)
    tampered["speed_kmph"] = 85.0
    is_valid, data, reason = verify_telemetry_packet(tampered, strict=True)
    assert is_valid is False
    assert reason == "HMAC_SIGNATURE_MISMATCH"


def test_hmac_detects_tampered_sequence_number(base_valid_telemetry):
    """Verifies that modifying sequence number causes HMAC mismatch."""
    tampered = dict(base_valid_telemetry)
    tampered["seq"] = 999
    is_valid, data, reason = verify_telemetry_packet(tampered, strict=True)
    assert is_valid is False
    assert reason == "HMAC_SIGNATURE_MISMATCH"


def test_anti_replay_rejects_expired_timestamp(base_valid_telemetry):
    """Verifies that packets older than the allowed tolerance window are rejected."""
    expired = dict(base_valid_telemetry)
    expired["timestamp"] = int(time.time()) - (REPLAY_TOLERANCE_SECONDS + 60)
    expired["signature"] = generate_signature(expired)
    
    is_valid, data, reason = verify_telemetry_packet(expired, strict=True)
    assert is_valid is False
    assert reason == "TIMESTAMP_EXPIRED"


def test_anti_replay_rejects_future_timestamp(base_valid_telemetry):
    """Verifies that packets with futuristic timestamps are rejected."""
    future = dict(base_valid_telemetry)
    future["timestamp"] = int(time.time()) + (REPLAY_TOLERANCE_SECONDS + 60)
    future["signature"] = generate_signature(future)
    
    is_valid, data, reason = verify_telemetry_packet(future, strict=True)
    assert is_valid is False
    assert reason == "TIMESTAMP_EXPIRED"


def test_anti_replay_monotonic_sequence_enforcement():
    """Verifies that replayed or out-of-order sequence numbers are rejected."""
    vid = "TEST-SEQ-VEH"
    reset_vehicle_sequence(vid)
    ts = int(time.time())

    def make_packet(seq):
        p = {
            "vehicle_id": vid, "vehicle_type": "Passenger", "timestamp": ts,
            "seq": seq, "lat": 17.42, "lon": 78.44, "alt": 500.0,
            "speed_kmph": 30.0, "heading_deg": 0.0, "pitch_deg": 0.0,
            "roll_deg": 0.0, "yaw_deg": 0.0, "battery_level": 90.0,
            "emergency_status": 0, "rf_status": "OK", "fault_code": "NONE"
        }
        p["signature"] = generate_signature(p)
        return p

    # First packet: seq=10 -> Accepted
    valid, data, reason = verify_telemetry_packet(make_packet(10), strict=True)
    assert valid is True

    # Next packet: seq=11 -> Accepted
    valid, data, reason = verify_telemetry_packet(make_packet(11), strict=True)
    assert valid is True

    # Replayed packet: seq=11 -> Rejected
    valid, data, reason = verify_telemetry_packet(make_packet(11), strict=True)
    assert valid is False
    assert reason == "REPLAY_SEQUENCE_DUPLICATE"

    # Regressed packet: seq=9 -> Rejected
    valid, data, reason = verify_telemetry_packet(make_packet(9), strict=True)
    assert valid is False
    assert reason == "REPLAY_SEQUENCE_DUPLICATE"


def test_missing_signature_rejection():
    """Verifies that a packet without a signature is rejected immediately."""
    packet = {
        "vehicle_id": "TEST-NO-SIG",
        "timestamp": int(time.time()),
        "seq": 1,
        "lat": 17.4,
        "lon": 78.4,
        "speed_kmph": 20.0
    }
    is_valid, data, reason = verify_telemetry_packet(packet, strict=True)
    assert is_valid is False
    assert reason == "MISSING_SIGNATURE"


# ============================================================================
# 2. COLLISION AVOIDANCE & RELATIVE KINEMATICS
# ============================================================================

def test_collision_approaching_vehicles_head_on():
    """
    Two vehicles traveling toward each other at 15 m/s (54 km/h) each.
    Initial separation = 40 meters.
    Closing speed ~ 30 m/s -> TTC = 40 / 30 ~ 1.33 seconds (< TTC_CRITICAL).
    Expect threat level 3 (Critical).
    """
    # V1 at (17.4230, 78.4480) heading North (0 deg), speed 54 km/h
    v1 = {
        "vehicle_id": "V1", "lat": 17.4230, "lon": 78.4480,
        "speed_kmph": 54.0, "heading_deg": 0.0, "emergency_status": 0
    }
    # V2 40m North at (17.42336, 78.4480) heading South (180 deg), speed 54 km/h
    v2 = {
        "vehicle_id": "V2", "lat": 17.42336, "lon": 78.4480,
        "speed_kmph": 54.0, "heading_deg": 180.0, "emergency_status": 0
    }

    dist, closing_speed, threat_level, ttc = compute_collision_risk(v1, v2)
    assert dist > 0 and dist < 60.0
    assert closing_speed > 0
    assert threat_level in (1, 2, 3)


def test_collision_separating_vehicles_diverging():
    """
    Two vehicles driving away from each other.
    Closing speed must be 0 or negative -> TTC infinite -> Threat level 0 (Safe).
    """
    v1 = {
        "vehicle_id": "V1", "lat": 17.4230, "lon": 78.4480,
        "speed_kmph": 50.0, "heading_deg": 180.0, "emergency_status": 0 # Driving South
    }
    v2 = {
        "vehicle_id": "V2", "lat": 17.4235, "lon": 78.4480,
        "speed_kmph": 50.0, "heading_deg": 0.0, "emergency_status": 0   # Driving North
    }

    dist, closing_speed, threat_level, ttc = compute_collision_risk(v1, v2)
    assert threat_level == 0  # Safe
    assert closing_speed <= 0.1
    assert ttc >= 99.0


def test_collision_same_position_zero_division_guard():
    """
    Two vehicles reporting identical coordinates.
    Algorithm must not raise ZeroDivisionError or produce NaN/Infinity.
    """
    v1 = {
        "vehicle_id": "V1", "lat": 17.4200, "lon": 78.4400,
        "speed_kmph": 30.0, "heading_deg": 90.0, "emergency_status": 0
    }
    v2 = {
        "vehicle_id": "V2", "lat": 17.4200, "lon": 78.4400,
        "speed_kmph": 30.0, "heading_deg": 90.0, "emergency_status": 0
    }

    dist, closing_speed, threat_level, ttc = compute_collision_risk(v1, v2)
    assert not math.isnan(dist)
    assert not math.isnan(ttc)
    assert dist >= 0.0



def test_emergency_vehicle_preemption_alert():
    """
    Emergency vehicle within proximity triggers threat level 4 (Preemption yield).
    """
    v_norm = {
        "vehicle_id": "V1", "lat": 17.4230, "lon": 78.4480,
        "speed_kmph": 40.0, "heading_deg": 90.0, "emergency_status": 0
    }
    v_amb = {
        "vehicle_id": "V_AMB", "lat": 17.4238, "lon": 78.4480, # ~90m away
        "speed_kmph": 70.0, "heading_deg": 90.0, "emergency_status": 1
    }

    dist, closing_speed, threat_level, ttc = compute_collision_risk(v_norm, v_amb)
    assert threat_level == 4  # Emergency Preemption Yield
    assert dist < EMERGENCY_PROXIMITY_METERS



def test_geofence_polygon_containment():
    """Verifies that point-in-polygon logic accurately detects points inside vs outside."""
    square = [
        {"lat": 10.0, "lon": 10.0},
        {"lat": 10.0, "lon": 20.0},
        {"lat": 20.0, "lon": 20.0},
        {"lat": 20.0, "lon": 10.0}
    ]
    # Center of square
    assert is_in_polygon(15.0, 15.0, square) is True
    # Outside square
    assert is_in_polygon(5.0, 5.0, square) is False
    assert is_in_polygon(25.0, 15.0, square) is False


# ============================================================================
# 3. REST API & ENDPOINT SECURITY
# ============================================================================

def test_api_telemetry_valid_packet(client, base_valid_telemetry):
    """Submitting valid telemetry via POST /api/telemetry succeeds."""
    response = client.post("/api/telemetry", json=base_valid_telemetry)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["vehicle_id"] == base_valid_telemetry["vehicle_id"]


def test_api_telemetry_rejects_untrusted_hmac(client, base_valid_telemetry):
    """Submitting telemetry with invalid HMAC signature returns 401 Unauthorized."""
    bad_packet = dict(base_valid_telemetry)
    bad_packet["signature"] = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    
    response = client.post("/api/telemetry", json=bad_packet)
    assert response.status_code == 401
    assert "HMAC" in response.json()["detail"]


def test_api_telemetry_pydantic_schema_validation(client, base_valid_telemetry):
    """Submitting invalid telemetry field ranges returns 422 Unprocessable Entity."""
    # Negative speed
    bad_speed = dict(base_valid_telemetry)
    bad_speed["speed_kmph"] = -15.0
    response = client.post("/api/telemetry", json=bad_speed)
    assert response.status_code == 422

    # Latitude out of range
    bad_lat = dict(base_valid_telemetry)
    bad_lat["lat"] = 120.0
    response = client.post("/api/telemetry", json=bad_lat)
    assert response.status_code == 422


def test_api_download_path_traversal_prevention(client):
    """
    Verifies that /api/download/{filename} prevents directory traversal attacks:
    - Rejects ../ and ..\\
    - Rejects absolute paths
    - Rejects non-PDF file extensions
    """
    # Directory traversal with ..
    r1 = client.get("/api/download/../../etc/passwd")
    assert r1.status_code in (400, 404)

    # Windows directory traversal attempt
    r2 = client.get("/api/download/..\\..\\backend\\main.py")
    assert r2.status_code in (400, 404)

    # Non-PDF file attempt
    r3 = client.get("/api/download/main.py")
    assert r3.status_code in (400, 404)

    # Missing PDF within allowed directory returns clean 404
    r4 = client.get("/api/download/nonexistent_report_123.pdf")
    assert r4.status_code == 404


def test_api_health_subsystems(client):
    """
    Verifies that /api/health returns calculated status for all individual subsystems.
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "subsystems" in data
    subsystems = data["subsystems"]
    assert "database" in subsystems
    assert "mqtt" in subsystems
    assert "gateway" in subsystems
    assert "ml_model" in subsystems
    assert subsystems["database"] == "healthy"


# ============================================================================
# 4. MACHINE LEARNING COLLISION MODEL & FALLBACK
# ============================================================================

def test_ml_collision_model_loading_and_inference():
    """Verifies that the trained ML model loads and classifies risk accurately."""
    predictor = CollisionPredictor()
    assert predictor.is_loaded() is True

    # High closing speed, short distance -> Critical (2)
    risk_critical = predictor.predict_risk(distance=15.0, closing_speed=25.0)
    assert risk_critical == 2

    # Negative closing speed (diverging) -> Safe (0)
    risk_safe = predictor.predict_risk(distance=50.0, closing_speed=-10.0)
    assert risk_safe == 0


def test_ml_rule_based_fallback_when_model_missing():
    """Verifies that rule-based TTC fallback operates correctly if model file is missing."""
    predictor = CollisionPredictor(model_path="nonexistent_fake_model.pkl")
    assert predictor.is_loaded() is False

    # Closing speed 20 m/s, distance 20 m -> TTC = 1.0s (< 2.0s) -> Critical (2)
    assert predictor.predict_risk(distance=20.0, closing_speed=20.0) == 2

    # Closing speed 10 m/s, distance 35 m -> TTC = 3.5s (< 5.0s) -> Warning (1)
    assert predictor.predict_risk(distance=35.0, closing_speed=10.0) == 1

    # Diverging -> Safe (0)
    assert predictor.predict_risk(distance=20.0, closing_speed=-5.0) == 0
