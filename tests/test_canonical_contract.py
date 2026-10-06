"""
Canonical Telemetry Contract Verification Tests
================================================
Validates that Python backend, Pydantic TelemetryPayload, HMAC signing,
and Edge serialization comply strictly with docs/CANONICAL_TELEMETRY_CONTRACT.md.
"""

import os
import sys
import time
import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import TelemetryPayload
from backend.security import (
    build_canonical_signing_string,
    generate_signature,
    verify_telemetry_packet,
    reset_vehicle_sequence
)
from backend.config import MAX_VALID_SPEED_KMPH


def test_canonical_signing_string_formatting():
    """Validates exact deterministic serialization string output."""
    data = {
        "vehicle_id": "V1",
        "vehicle_type": "Passenger",
        "timestamp": 1730000000,
        "seq": 105,
        "lat": 17.42390012,   # Should be truncated/rounded to 6 decimal places: 17.423900
        "lon": 78.44830089,   # Should be truncated/rounded to 6 decimal places: 78.448301
        "speed_kmph": 42.54,  # Should be formatted to 1 decimal place: 42.5
        "heading_deg": 89.6   # Should be rounded to integer degree: 90
    }
    canonical = build_canonical_signing_string(data)
    expected = (
        "vehicle_id=V1|vehicle_type=Passenger|timestamp=1730000000|seq=105|"
        "lat=17.423900|lon=78.448301|speed_kmph=42.5|heading_deg=90"
    )
    assert canonical == expected


def test_canonical_contract_valid_payload():
    """Ensures a compliant contract payload passes both Pydantic and HMAC validation."""
    reset_vehicle_sequence("CONTRACT-V1")
    ts = int(time.time())
    payload_dict = {
        "vehicle_id": "CONTRACT-V1",
        "vehicle_type": "Passenger",
        "timestamp": ts,
        "seq": 1,
        "lat": 17.423900,
        "lon": 78.448300,
        "alt": 542.0,
        "speed_kmph": 50.0,
        "heading_deg": 90.0,
        "pitch_deg": 1.2,
        "roll_deg": -0.8,
        "yaw_deg": 90.0,
        "battery_level": 98.5,
        "emergency_status": 0,
        "rf_status": "OK",
        "fault_code": "NONE"
    }
    payload_dict["signature"] = generate_signature(payload_dict)

    # 1. Pydantic validation
    pydantic_obj = TelemetryPayload(**payload_dict)
    assert pydantic_obj.vehicle_id == "CONTRACT-V1"
    assert pydantic_obj.speed_kmph == 50.0

    # 2. Cryptographic and anti-replay verification
    is_valid, verified_data, reason = verify_telemetry_packet(payload_dict, strict=True)
    assert is_valid is True
    assert reason == "OK"


@pytest.mark.parametrize("invalid_field,invalid_value", [
    ("lat", 91.0),                  # Latitude > 90
    ("lat", -91.0),                 # Latitude < -90
    ("lon", 181.0),                 # Longitude > 180
    ("lon", -181.0),                # Longitude < -180
    ("speed_kmph", -5.0),           # Negative speed
    ("speed_kmph", MAX_VALID_SPEED_KMPH + 10.0), # Speed > 250 km/h
    ("seq", -1),                    # Negative sequence
    ("heading_deg", 365.0),         # Heading > 360
    ("emergency_status", 2),        # Emergency status must be 0 or 1
])
def test_canonical_contract_out_of_bounds_rejection(invalid_field, invalid_value):
    """Verifies that Pydantic rejects telemetry packets violating physical bounds."""
    base = {
        "vehicle_id": "V1",
        "vehicle_type": "Passenger",
        "timestamp": int(time.time()),
        "seq": 10,
        "lat": 17.423900,
        "lon": 78.448300,
        "alt": 542.0,
        "speed_kmph": 45.0,
        "heading_deg": 90.0,
        "pitch_deg": 0.0,
        "roll_deg": 0.0,
        "yaw_deg": 90.0,
        "battery_level": 100.0,
        "emergency_status": 0,
        "rf_status": "OK",
        "fault_code": "NONE",
        "signature": "dummy_signature"
    }
    base[invalid_field] = invalid_value
    with pytest.raises(ValidationError):
        TelemetryPayload(**base)
