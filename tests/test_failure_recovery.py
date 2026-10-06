"""
Automated Failure and Recovery Test Suite
=========================================
Validates the failure and recovery behaviors documented in docs/FAILURE_AND_RECOVERY_MATRIX.md.
Tests system reactions against:
- Malformed JSON packets (REJECTED)
- Invalid cryptographic HMAC signatures (REJECTED)
- Expired timestamps (REJECTED)
- Repeated and regressive sequence numbers (REJECTED)
- Microcontroller reboot sequence reset (RECOVERED)
- Invalid GNSS coordinate inputs (FAIL-SAFE)
- Missing Machine Learning model artifact (DEGRADED)
- MQTT broker unavailability fallback (DEGRADED)
- WebSocket client disconnection (RECOVERED)
"""

import os
import sys
import time
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.security import (
    verify_telemetry_packet,
    generate_signature,
    reset_vehicle_sequence
)
from backend.mqtt_client import (
    compute_collision_risk,
    publish_or_dispatch,
    is_mqtt_connected
)
from ml.collision_model import CollisionPredictor


@pytest.fixture
def client():
    return TestClient(app)


def test_failure_malformed_json_rejected():
    """Validates that corrupt, non-JSON telemetry frames are REJECTED."""
    is_valid, data, reason = verify_telemetry_packet("NOT_VALID_JSON{:::}")
    assert is_valid is False
    assert reason == "MALFORMED_JSON"


def test_failure_invalid_hmac_rejected():
    """Validates that untrusted signatures are REJECTED."""
    raw = {
        "vehicle_id": "ROGUE",
        "timestamp": int(time.time()),
        "seq": 1,
        "lat": 17.42,
        "lon": 78.44,
        "speed_kmph": 50.0,
        "heading_deg": 90.0,
        "signature": "00" * 32
    }
    is_valid, data, reason = verify_telemetry_packet(raw, strict=True)
    assert is_valid is False
    assert reason == "HMAC_SIGNATURE_MISMATCH"


def test_failure_expired_timestamp_rejected():
    """Validates that expired packets are REJECTED."""
    pkt = {
        "vehicle_id": "EXPIRED-V1",
        "timestamp": int(time.time()) - 120, # 2 minutes old
        "seq": 1,
        "lat": 17.42,
        "lon": 78.44,
        "speed_kmph": 30.0,
        "heading_deg": 90.0
    }
    pkt["signature"] = generate_signature(pkt)
    is_valid, data, reason = verify_telemetry_packet(pkt, strict=True)
    assert is_valid is False
    assert reason == "TIMESTAMP_EXPIRED"


def test_failure_duplicate_sequence_rejected():
    """Validates that duplicate sequence numbers are REJECTED."""
    vid = "DUP-SEQ-V1"
    reset_vehicle_sequence(vid)
    ts = int(time.time())

    p1 = {
        "vehicle_id": vid, "timestamp": ts, "seq": 50,
        "lat": 17.42, "lon": 78.44, "speed_kmph": 30.0, "heading_deg": 90.0
    }
    p1["signature"] = generate_signature(p1)
    ok1, _, _ = verify_telemetry_packet(p1, strict=True)
    assert ok1 is True

    # Duplicate sequence 50
    ok2, _, reason = verify_telemetry_packet(p1, strict=True)
    assert ok2 is False
    assert reason == "REPLAY_SEQUENCE_DUPLICATE"


def test_recovery_microcontroller_reboot():
    """Validates that a node reboot (seq drops to <= 5 with advance in time) is RECOVERED."""
    vid = "REBOOT-NODE-V1"
    reset_vehicle_sequence(vid)
    t0 = int(time.time())

    # Initial operating state at sequence 85
    p_pre = {
        "vehicle_id": vid, "timestamp": t0, "seq": 85,
        "lat": 17.42, "lon": 78.44, "speed_kmph": 30.0, "heading_deg": 90.0
    }
    p_pre["signature"] = generate_signature(p_pre)
    assert verify_telemetry_packet(p_pre, strict=True)[0] is True

    # Node reboots and begins transmitting from sequence 1 at t0 + 1
    p_post = {
        "vehicle_id": vid, "timestamp": t0 + 1, "seq": 1,
        "lat": 17.42, "lon": 78.44, "speed_kmph": 30.0, "heading_deg": 90.0
    }
    p_post["signature"] = generate_signature(p_post)
    ok_reboot, _, reason = verify_telemetry_packet(p_post, strict=True)
    assert ok_reboot is True
    assert reason == "OK"


def test_failsafe_invalid_gnss_coordinates():
    """Validates that non-numeric or missing GNSS coordinates trigger a safe return posture."""
    v1 = {"vehicle_id": "V1", "lat": "INVALID", "lon": None, "speed_kmph": 50.0}
    v2 = {"vehicle_id": "V2", "lat": 17.42, "lon": 78.44, "speed_kmph": 50.0}
    dist, closing_speed, risk, ttc = compute_collision_risk(v1, v2)
    assert dist == 999.0
    assert closing_speed == 0.0
    assert risk == 0
    assert ttc == 99.9


def test_degraded_ml_model_missing():
    """Validates that missing ML model degrades gracefully to deterministic rule-based TTC."""
    predictor = CollisionPredictor(model_path="nonexistent_mock_file.pkl")
    assert predictor.is_loaded() is False

    # Imminent hazard: distance 15m, closing speed 15 m/s -> TTC = 1.0s -> Critical (2)
    risk = predictor.predict_risk(distance=15.0, closing_speed=15.0)
    assert risk == 2

    # Warning hazard: distance 30m, closing speed 10 m/s -> TTC = 3.0s -> Warning (1)
    risk_warn = predictor.predict_risk(distance=30.0, closing_speed=10.0)
    assert risk_warn == 1

    # Safe: separating
    risk_safe = predictor.predict_risk(distance=30.0, closing_speed=-5.0)
    assert risk_safe == 0


def test_degraded_mqtt_offline_direct_dispatch():
    """Validates that if MQTT is disconnected, publish_or_dispatch processes in-memory without crash."""
    reset_vehicle_sequence("DISPATCH-TEST")
    pkt = {
        "vehicle_id": "DISPATCH-TEST", "vehicle_type": "Passenger", "timestamp": int(time.time()),
        "seq": 1, "lat": 17.42, "lon": 78.44, "alt": 500.0, "speed_kmph": 35.0,
        "heading_deg": 90.0, "pitch_deg": 0.0, "roll_deg": 0.0, "yaw_deg": 90.0,
        "battery_level": 99.0, "emergency_status": 0, "rf_status": "OK", "fault_code": "NONE"
    }
    pkt["signature"] = generate_signature(pkt)
    # Should not raise exception even when broker is unreachable
    publish_or_dispatch("v2v/telemetry", str(pkt).replace("'", '"'))


def test_recovery_websocket_clean_disconnect(client):
    """Validates that WebSocket connections cleanly terminate upon client disconnect."""
    with client.websocket_connect("/ws") as ws:
        data = ws.receive_json()
        assert data["type"] == "init_state"
    # Scope exits and disconnects socket; server cleanly cleans up client handle without unhandled exceptions
