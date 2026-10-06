"""
V2V-SCADA Vehicular Traffic & Collision Scenario Simulator
==========================================================
Generates realistic 10Hz synthetic vehicle telemetry streams.
All emitted data is explicitly marked with `"data_source": "SIMULATED"` to
prevent confusion with real physical hardware transmissions.

Supported Scenarios (--scenario):
- `default`: Standard 4-vehicle highway loop over OSRM road geometry.
- `head_on`: Two passenger vehicles converging on a head-on collision path.
- `crossing`: Two vehicles approaching an unsignalized perpendicular crossing.
- `following`: Rapidly closing rear-end collision scenario.
- `emergency`: High-speed emergency ambulance preemption yield scenario.
- `geofence`: Vehicle intentionally breaching restricted highway construction zone.
"""

import paho.mqtt.client as mqtt
import time
import json
import math
import random
import os
import sys
import argparse

# Ensure backend modules can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.security import generate_signature
from backend.config import MQTT_BROKER, MQTT_PORT, MQTT_TOPIC_TELEMETRY
from backend.mqtt_client import publish_or_dispatch

mqtt_active = False

def on_connect(client, userdata, flags, rc):
    global mqtt_active
    if rc == 0:
        mqtt_active = True
        print("[Simulator] Connected to Mosquitto MQTT Broker!")
    else:
        mqtt_active = False
        print(f"[Simulator] Failed to connect to MQTT broker, code {rc}")

def get_scenario_vehicles(scenario: str):
    """Returns vehicle configurations and initial states for the selected scenario."""
    if scenario == "head_on":
        print("[Simulator] SCENARIO: Head-on Collision Convergence")
        return [
            {"id": "V1", "type": "Passenger", "idx": 0.0, "speed": 54.0, "heading": 90.0,  "lat": 17.4239, "lon": 78.4450, "route": None, "rate": 0.0},
            {"id": "V2", "type": "Passenger", "idx": 0.0, "speed": 54.0, "heading": 270.0, "lat": 17.4239, "lon": 78.4510, "route": None, "rate": 0.0},
        ]
    elif scenario == "crossing":
        print("[Simulator] SCENARIO: Perpendicular Crossing Hazard")
        return [
            {"id": "V1", "type": "Passenger", "idx": 0.0, "speed": 45.0, "heading": 0.0,  "lat": 17.4210, "lon": 78.4483, "route": None, "rate": 0.0},
            {"id": "V2", "type": "Passenger", "idx": 0.0, "speed": 45.0, "heading": 90.0, "lat": 17.4239, "lon": 78.4450, "route": None, "rate": 0.0},
        ]
    elif scenario == "following":
        print("[Simulator] SCENARIO: High-Speed Rear-End Following Hazard")
        return [
            {"id": "V1", "type": "Passenger", "idx": 0.0, "speed": 30.0, "heading": 0.0, "lat": 17.4245, "lon": 78.4483, "route": None, "rate": 0.0},
            {"id": "V2", "type": "Passenger", "idx": 0.0, "speed": 75.0, "heading": 0.0, "lat": 17.4230, "lon": 78.4483, "route": None, "rate": 0.0},
        ]
    elif scenario == "emergency":
        print("[Simulator] SCENARIO: Emergency Vehicle Preemption Yield")
        return [
            {"id": "V1", "type": "Passenger", "idx": 0.0, "speed": 40.0, "heading": 0.0, "lat": 17.4235, "lon": 78.4483, "route": None, "rate": 0.0},
            {"id": "V4", "type": "Emergency", "idx": 0.0, "speed": 85.0, "heading": 0.0, "lat": 17.4215, "lon": 78.4483, "route": None, "rate": 0.0},
        ]
    elif scenario == "geofence":
        print("[Simulator] SCENARIO: Restricted Highway Geofence Breach")
        return [
            {"id": "V1", "type": "Passenger", "idx": 0.0, "speed": 50.0, "heading": 180.0, "lat": 17.4260, "lon": 78.4490, "route": None, "rate": 0.0},
        ]
    else:
        print("[Simulator] SCENARIO: Default 4-Vehicle Highway Loop (OSRM Geometry)")
        return [
            {"id": "V1", "type": "Passenger", "idx": 0.0, "speed": 48.0, "heading": 90.0,  "lat": 17.4239, "lon": 78.4400, "route": "v1", "rate": 0.16},
            {"id": "V2", "type": "Passenger", "idx": 0.0, "speed": 52.0, "heading": 270.0, "lat": 17.4239, "lon": 78.4550, "route": "v2", "rate": 0.22},
            {"id": "V3", "type": "Truck",     "idx": 0.0, "speed": 36.0, "heading": 0.0,   "lat": 17.4180, "lon": 78.4483, "route": "v3", "rate": 0.12},
            {"id": "V4", "type": "Emergency", "idx": 0.0, "speed": 75.0, "heading": 180.0, "lat": 17.4290, "lon": 78.4483, "route": "v4", "rate": 0.32},
        ]

def run_simulation(scenario: str = "default", max_seconds: float = None):
    global mqtt_active
    client = mqtt.Client(client_id="STM32_Vehicular_Traffic_Simulator")
    client.on_connect = on_connect

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 10)
        client.loop_start()
        mqtt_active = True
    except Exception as e:
        mqtt_active = False
        print(f"[Simulator] Note: Mosquitto broker not running ({e}). Operating in Autonomous Direct-Dispatch Mode.")

    # Load OSRM routes if available
    routes_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend', 'routes.json')
    routes = None
    if os.path.exists(routes_path):
        try:
            with open(routes_path, 'r') as f:
                routes = json.load(f)
        except Exception:
            routes = None

    vehicles = get_scenario_vehicles(scenario)
    seq_tracker = {v["id"]: 0 for v in vehicles}
    start_time = time.time()
    print(f"[Simulator] Running '{scenario}' scenario at 10Hz. (Ctrl+C to stop)")

    try:
        while True:
            if max_seconds and (time.time() - start_time) >= max_seconds:
                break

            timestamp = int(time.time())
            dt = 0.1

            for v in vehicles:
                vid = v["id"]
                seq_tracker[vid] += 1

                # Update position along route or algorithmic trajectory
                if routes and v["route"] and v["route"] in routes:
                    route_pts = routes[v["route"]]
                    v["idx"] += v["rate"]
                    pt_idx = min(len(route_pts) - 1, int(v["idx"]))
                    v["lon"], v["lat"] = route_pts[pt_idx]
                    if v["idx"] >= len(route_pts) - 1:
                        v["idx"] = 0.0
                else:
                    heading_rad = math.radians(v["heading"])
                    v["lat"] += (v["speed"] / 3600.0) * dt * math.cos(heading_rad) / 111.0
                    v["lon"] += (v["speed"] / 3600.0) * dt * math.sin(heading_rad) / (111.0 * math.cos(math.radians(v["lat"])))

                # Road dynamics jitter
                pitch_deg = round(math.sin(time.time() * 2 + seq_tracker[vid]) * 1.5, 1)
                roll_deg = round(math.cos(time.time() * 1.5 + seq_tracker[vid]) * 2.2, 1)
                alt = 542.0 + round(math.sin(v["lat"] * 1000) * 12.0, 1)

                telemetry = {
                    "vehicle_id": vid,
                    "vehicle_type": v["type"],
                    "timestamp": timestamp,
                    "seq": seq_tracker[vid],
                    "lat": round(v["lat"], 6),
                    "lon": round(v["lon"], 6),
                    "alt": alt,
                    "speed_kmph": round(v["speed"], 1),
                    "heading_deg": round(v["heading"], 1),
                    "pitch_deg": pitch_deg,
                    "roll_deg": roll_deg,
                    "yaw_deg": round(v["heading"], 1),
                    "battery_level": round(98.0 - (seq_tracker[vid] * 0.001), 1),
                    "emergency_status": 1 if v["type"] == "Emergency" else 0,
                    "rf_status": "OK",
                    "fault_code": "NONE",
                    "data_source": "SIMULATED"
                }

                # Cryptographically sign packet
                telemetry["signature"] = generate_signature(telemetry)

                raw_payload = json.dumps(telemetry)
                if mqtt_active:
                    client.publish(MQTT_TOPIC_TELEMETRY, raw_payload)
                else:
                    publish_or_dispatch(MQTT_TOPIC_TELEMETRY, raw_payload)

            time.sleep(0.1)  # 10Hz broadcast interval

    except KeyboardInterrupt:
        print("\n[Simulator] Simulation stopped by user.")
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description="V2V-SCADA Vehicular Traffic & Scenario Simulator")
    parser.add_argument(
        "--scenario",
        choices=["default", "head_on", "crossing", "following", "emergency", "geofence"],
        default="default",
        help="Select scenario preset to execute"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Maximum run time in seconds (default: indefinite)"
    )
    args = parser.parse_args()
    run_simulation(scenario=args.scenario, max_seconds=args.duration)

if __name__ == "__main__":
    main()
