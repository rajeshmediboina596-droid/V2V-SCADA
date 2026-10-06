"""
Deterministic Collision Engine Test Suite (16 Core Scenarios)
==============================================================
Validates the V2V-SCADA 2D kinematic relative-motion and Time-to-Collision (TTC) engine.
Coverage of all 16 prescribed test scenarios:
 1. Head-on approaching vehicles
 2. Vehicles moving apart
 3. Parallel vehicles
 4. Stationary vehicles
 5. One stationary + one approaching
 6. Zero closing speed
 7. Very high closing speed
 8. Invalid GNSS
 9. Stale telemetry pruning
10. Same coordinates (Singularity guard)
11. Heading 359° -> 0° wrap-around
12. Emergency vehicle preemption
13. Geofence violation
14. Warning TTC threshold
15. Critical TTC threshold
16. Safe TTC threshold

Mathematical Assumptions:
- WGS-84 coordinates projected locally into metric Cartesian displacement:
  dx = (lon2 - lon1) * 111320 * cos(mid_lat)
  dy = (lat2 - lat1) * 111320
- Compass heading angles: 0 deg = North (+Y), 90 deg = East (+X), 180 deg = South (-Y), 270 deg = West (-X).
- Closing speed is line-of-sight velocity projection: dot(r_rel, v_rel) / |r_rel|.
- TTC = distance / closing_speed (when closing_speed > 0.5 m/s, else 99.9s).
- Note: This is an academic/engineering prototype relative-motion model.
"""

import os
import sys
import math
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.mqtt_client import (
    compute_collision_risk,
    is_in_polygon,
    vehicle_states,
    process_telemetry_payload
)
from backend.config import RESTRICTED_ZONE, EMERGENCY_PROXIMITY_METERS
from backend.security import generate_signature, reset_vehicle_sequence


# -----------------------------------------------------------------------------
# Scenario 1: Head-on approaching vehicles
# -----------------------------------------------------------------------------
def test_scenario_01_head_on_approaching():
    v1 = {"vehicle_id": "V1", "lat": 17.4230, "lon": 78.4480, "speed_kmph": 54.0, "heading_deg": 0.0}     # North 15 m/s
    v2 = {"vehicle_id": "V2", "lat": 17.42336, "lon": 78.4480, "speed_kmph": 54.0, "heading_deg": 180.0} # South 15 m/s (~40m apart)
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v1, v2)
    assert 30.0 < dist < 50.0
    assert 28.0 < closing_speed < 32.0  # ~30 m/s relative approach
    assert ttc < 2.0
    assert risk_level in (1, 2)


# -----------------------------------------------------------------------------
# Scenario 2: Vehicles moving apart (diverging)
# -----------------------------------------------------------------------------
def test_scenario_02_vehicles_moving_apart():
    v1 = {"vehicle_id": "V1", "lat": 17.4230, "lon": 78.4480, "speed_kmph": 50.0, "heading_deg": 180.0} # Driving South
    v2 = {"vehicle_id": "V2", "lat": 17.4235, "lon": 78.4480, "speed_kmph": 50.0, "heading_deg": 0.0}   # Driving North
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v1, v2)
    assert dist > 0
    assert closing_speed == 0.0  # Diverging speed clamped to 0
    assert ttc >= 99.0
    assert risk_level == 0


# -----------------------------------------------------------------------------
# Scenario 3: Parallel vehicles in adjacent lanes
# -----------------------------------------------------------------------------
def test_scenario_03_parallel_vehicles():
    v1 = {"vehicle_id": "V1", "lat": 17.4230, "lon": 78.4480, "speed_kmph": 60.0, "heading_deg": 90.0}      # East 60 km/h
    v2 = {"vehicle_id": "V2", "lat": 17.4231, "lon": 78.4480, "speed_kmph": 60.0, "heading_deg": 90.0}      # East 60 km/h (11m North)
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v1, v2)
    assert 9.0 < dist < 15.0
    assert closing_speed < 0.1  # Same speed & direction -> zero approach along vector
    assert ttc >= 99.0
    assert risk_level == 0


# -----------------------------------------------------------------------------
# Scenario 4: Both vehicles stationary
# -----------------------------------------------------------------------------
def test_scenario_04_both_stationary():
    v1 = {"vehicle_id": "V1", "lat": 17.4230, "lon": 78.4480, "speed_kmph": 0.0, "heading_deg": 0.0}
    v2 = {"vehicle_id": "V2", "lat": 17.4232, "lon": 78.4480, "speed_kmph": 0.0, "heading_deg": 0.0}
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v1, v2)
    assert dist > 15.0
    assert closing_speed == 0.0
    assert ttc >= 99.0
    assert risk_level == 0


# -----------------------------------------------------------------------------
# Scenario 5: One stationary + one approaching (rear-end risk)
# -----------------------------------------------------------------------------
def test_scenario_05_one_stationary_one_approaching():
    v_stopped = {"vehicle_id": "V1", "lat": 17.42345, "lon": 78.4480, "speed_kmph": 0.0, "heading_deg": 0.0}
    v_approaching = {"vehicle_id": "V2", "lat": 17.4230, "lon": 78.4480, "speed_kmph": 72.0, "heading_deg": 0.0} # 20 m/s North
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v_approaching, v_stopped)
    assert 40.0 < dist < 60.0
    assert 18.0 < closing_speed < 22.0
    assert ttc < 3.5
    assert risk_level > 0


# -----------------------------------------------------------------------------
# Scenario 6: Zero closing speed (tandem convoy following at same speed)
# -----------------------------------------------------------------------------
def test_scenario_06_zero_closing_speed_tandem():
    v_lead = {"vehicle_id": "V1", "lat": 17.4235, "lon": 78.4480, "speed_kmph": 80.0, "heading_deg": 0.0}
    v_follow = {"vehicle_id": "V2", "lat": 17.4232, "lon": 78.4480, "speed_kmph": 80.0, "heading_deg": 0.0}
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v_follow, v_lead)
    assert dist > 20.0
    assert closing_speed < 0.1
    assert ttc >= 99.0
    assert risk_level == 0


# -----------------------------------------------------------------------------
# Scenario 7: Very high closing speed (head-on highway)
# -----------------------------------------------------------------------------
def test_scenario_07_very_high_closing_speed():
    v1 = {"vehicle_id": "V1", "lat": 17.4220, "lon": 78.4480, "speed_kmph": 120.0, "heading_deg": 0.0}   # 33.3 m/s
    v2 = {"vehicle_id": "V2", "lat": 17.4230, "lon": 78.4480, "speed_kmph": 120.0, "heading_deg": 180.0} # 33.3 m/s (~111m apart)
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v1, v2)
    assert 100.0 < dist < 125.0
    assert 60.0 < closing_speed < 70.0
    assert ttc < 2.0
    assert risk_level == 2  # Critical threat level


# -----------------------------------------------------------------------------
# Scenario 8: Invalid GNSS coordinates
# -----------------------------------------------------------------------------
def test_scenario_08_invalid_gnss():
    v1 = {"vehicle_id": "V1", "lat": "NaN", "lon": 78.4480, "speed_kmph": 50.0, "heading_deg": 0.0}
    v2 = {"vehicle_id": "V2", "lat": 17.4230, "lon": "None", "speed_kmph": 50.0, "heading_deg": 0.0}
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v1, v2)
    assert dist == 999.0
    assert closing_speed == 0.0
    assert risk_level == 0
    assert ttc == 99.9


# -----------------------------------------------------------------------------
# Scenario 9: Stale telemetry pruning
# -----------------------------------------------------------------------------
def test_scenario_09_stale_telemetry_pruned():
    reset_vehicle_sequence("STALE-V1")
    now = time.time()
    vehicle_states["STALE-V1"] = {
        "vehicle_id": "STALE-V1", "vehicle_type": "Passenger", "timestamp": int(now - 25),
        "seq": 1, "lat": 17.4230, "lon": 78.4480, "speed_kmph": 40.0, "heading_deg": 90.0,
        "last_seen": now - 25.0  # Stale: > 15s expiry
    }
    # When a new packet arrives for another vehicle, stale vehicles are pruned
    fresh_packet = {
        "vehicle_id": "FRESH-V2", "vehicle_type": "Passenger", "timestamp": int(now),
        "seq": 1, "lat": 17.4231, "lon": 78.4481, "alt": 540.0, "speed_kmph": 40.0,
        "heading_deg": 90.0, "pitch_deg": 0.0, "roll_deg": 0.0, "yaw_deg": 90.0,
        "battery_level": 95.0, "emergency_status": 0, "rf_status": "OK", "fault_code": "NONE"
    }
    fresh_packet["signature"] = generate_signature(fresh_packet)
    reset_vehicle_sequence("FRESH-V2")
    process_telemetry_payload(str(fresh_packet).replace("'", '"'))
    assert "STALE-V1" not in vehicle_states


# -----------------------------------------------------------------------------
# Scenario 10: Same coordinates (Singularity division guard)
# -----------------------------------------------------------------------------
def test_scenario_10_same_coordinates_singularity():
    v1 = {"vehicle_id": "V1", "lat": 17.420000, "lon": 78.440000, "speed_kmph": 30.0, "heading_deg": 90.0}
    v2 = {"vehicle_id": "V2", "lat": 17.420000, "lon": 78.440000, "speed_kmph": 30.0, "heading_deg": 90.0}
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v1, v2)
    assert not math.isnan(dist)
    assert not math.isnan(closing_speed)
    assert not math.isnan(ttc)
    assert dist == 0.0


# -----------------------------------------------------------------------------
# Scenario 11: Heading 359° -> 0° wrap-around
# -----------------------------------------------------------------------------
def test_scenario_11_heading_wrap_around():
    # V1 heading 359.5° (nearly due North), V2 heading 0.5° (nearly due North)
    v1 = {"vehicle_id": "V1", "lat": 17.4230, "lon": 78.4480, "speed_kmph": 50.0, "heading_deg": 359.5}
    v2 = {"vehicle_id": "V2", "lat": 17.4235, "lon": 78.4480, "speed_kmph": 50.0, "heading_deg": 0.5}
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v1, v2)
    assert closing_speed < 0.5  # Virtually zero relative lateral drift
    assert not math.isnan(closing_speed)


# -----------------------------------------------------------------------------
# Scenario 12: Emergency vehicle preemption
# -----------------------------------------------------------------------------
def test_scenario_12_emergency_vehicle_preemption():
    v_norm = {"vehicle_id": "CIVILIAN", "lat": 17.4230, "lon": 78.4480, "speed_kmph": 40.0, "heading_deg": 90.0}
    v_amb = {
        "vehicle_id": "AMBULANCE", "vehicle_type": "Emergency", "emergency_status": 1,
        "lat": 17.4238, "lon": 78.4480, "speed_kmph": 70.0, "heading_deg": 90.0  # ~90m away
    }
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v_norm, v_amb)
    assert dist < EMERGENCY_PROXIMITY_METERS
    assert risk_level == 4  # Priority Preemption Yield


# -----------------------------------------------------------------------------
# Scenario 13: Geofence violation
# -----------------------------------------------------------------------------
def test_scenario_13_geofence_containment():
    # Inside Hyderabad NH-65 Test Corridor
    inside_lat, inside_lon = 17.4210, 78.4490
    assert is_in_polygon(inside_lat, inside_lon, RESTRICTED_ZONE) is True

    # Far outside test corridor
    outside_lat, outside_lon = 17.5000, 78.5000
    assert is_in_polygon(outside_lat, outside_lon, RESTRICTED_ZONE) is False


# -----------------------------------------------------------------------------
# Scenario 14: Warning TTC threshold
# -----------------------------------------------------------------------------
def test_scenario_14_warning_ttc_threshold():
    # Distance ~ 45m, approach rate 15 m/s -> TTC = 3.0s
    v1 = {"vehicle_id": "V1", "lat": 17.4230, "lon": 78.4480, "speed_kmph": 54.0, "heading_deg": 0.0}
    v2 = {"vehicle_id": "V2", "lat": 17.423405, "lon": 78.4480, "speed_kmph": 0.0, "heading_deg": 0.0}
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v1, v2)
    assert 2.5 <= ttc <= 3.5
    assert risk_level in (1, 2)


# -----------------------------------------------------------------------------
# Scenario 15: Critical TTC threshold (AEB intervention)
# -----------------------------------------------------------------------------
def test_scenario_15_critical_ttc_threshold():
    # Distance ~ 25m, approach rate 20 m/s -> TTC = 1.25s
    v1 = {"vehicle_id": "V1", "lat": 17.4230, "lon": 78.4480, "speed_kmph": 72.0, "heading_deg": 0.0}
    v2 = {"vehicle_id": "V2", "lat": 17.423225, "lon": 78.4480, "speed_kmph": 0.0, "heading_deg": 0.0}
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v1, v2)
    assert ttc <= 2.5
    assert risk_level == 2  # Critical Threat


# -----------------------------------------------------------------------------
# Scenario 16: Safe TTC threshold
# -----------------------------------------------------------------------------
def test_scenario_16_safe_ttc_threshold():
    # Distance ~ 150m, approach rate 10 m/s -> TTC = 15.0s
    v1 = {"vehicle_id": "V1", "lat": 17.4215, "lon": 78.4480, "speed_kmph": 36.0, "heading_deg": 0.0}
    v2 = {"vehicle_id": "V2", "lat": 17.4230, "lon": 78.4480, "speed_kmph": 0.0, "heading_deg": 0.0}
    dist, closing_speed, risk_level, ttc = compute_collision_risk(v1, v2)
    assert ttc > 5.0
    assert risk_level == 0  # Safe
