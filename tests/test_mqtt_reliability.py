"""
MQTT Reliability and Message Ingestion Tests
============================================
Validates MQTT callbacks, fallback dispatch, burst throughput,
and malformed frame rejection per docs/MQTT_RELIABILITY_SPEC.md.
"""

import os
import sys
import json
import time
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.mqtt_client import (
    on_connect,
    on_disconnect,
    on_message,
    publish_or_dispatch,
    gateway_health_state,
    vehicle_states
)
from backend.security import generate_signature, reset_vehicle_sequence


def test_mqtt_connect_disconnect_callbacks():
    """Validates MQTT on_connect and on_disconnect state flags."""
    mock_client = MagicMock()

    # Test successful connection (rc = 0)
    on_connect(mock_client, None, {}, 0)
    mock_client.subscribe.assert_any_call("v2v/telemetry")
    mock_client.subscribe.assert_any_call("v2v/gateway/health")

    # Test disconnection (rc != 0)
    on_disconnect(mock_client, None, 1)


def test_mqtt_gateway_health_message_ingest():
    """Validates that v2v/gateway/health messages update internal state dictionary."""
    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.topic = "v2v/gateway/health"
    health_data = {
        "node_id": "RSU-GATEWAY-TEST",
        "status": "Online",
        "port": "COM4",
        "packets_rx": 150,
        "timestamp": int(time.time())
    }
    mock_msg.payload = json.dumps(health_data).encode("utf-8")

    on_message(mock_client, None, mock_msg)
    assert gateway_health_state["port"] == "COM4"
    assert gateway_health_state["packets_rx"] == 150
    assert gateway_health_state["status"] == "Online"


def test_mqtt_malformed_telemetry_drops_cleanly():
    """Validates that corrupt payload on v2v/telemetry does not crash the on_message listener."""
    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.topic = "v2v/telemetry"
    mock_msg.payload = b"CORRUPTED_RAW_BYTES_NOT_JSON{{}"

    # Execution must complete gracefully without throwing unhandled exceptions
    on_message(mock_client, None, mock_msg)


def test_mqtt_burst_throughput_handling():
    """Validates rapid sequential ingestion of 50 packets without drops or exceptions."""
    vid = "BURST-VEH-01"
    reset_vehicle_sequence(vid)
    ts = int(time.time())

    for seq in range(1, 51):
        pkt = {
            "vehicle_id": vid,
            "vehicle_type": "Passenger",
            "timestamp": ts,
            "seq": seq,
            "lat": 17.4230 + (seq * 0.00001),
            "lon": 78.4480 + (seq * 0.00001),
            "alt": 540.0,
            "speed_kmph": 40.0,
            "heading_deg": 90.0,
            "pitch_deg": 0.0,
            "roll_deg": 0.0,
            "yaw_deg": 90.0,
            "battery_level": 98.0,
            "emergency_status": 0,
            "rf_status": "OK",
            "fault_code": "NONE"
        }
        pkt["signature"] = generate_signature(pkt)
        publish_or_dispatch("v2v/telemetry", json.dumps(pkt))

    assert vid in vehicle_states
    assert vehicle_states[vid]["seq"] == 50
