import paho.mqtt.client as mqtt
import time
import json
import math
import random
import os
import sys

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

def main():
    global mqtt_active
    client = mqtt.Client(client_id="STM32_Vehicular_Traffic_Simulator")
    client.on_connect = on_connect

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 10)
        client.loop_start()
        mqtt_active = True
    except Exception as e:
        mqtt_active = False
        print(f"[Simulator] Note: Mosquitto broker not running ({e}).")
        print("[Simulator] Operating in Autonomous Direct-Dispatch Mode (No external broker required).")

    # Load OSRM routes for real-world road curvature snapping
    routes_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend', 'routes.json')
    try:
        with open(routes_path, 'r') as f:
            routes = json.load(f)
            print("[Simulator] Loaded OSRM road geometry routes.")
    except Exception as e:
        print(f"[Simulator] Warning: routes.json not found ({e}). Falling back to algorithmic pathing.")
        routes = None

    # Define 4 primary vehicles (including Emergency vehicle V4)
    vehicles = [
        {"id": "V1", "type": "Passenger", "idx": 0.0, "speed": 48.0, "heading": 90.0,  "lat": 17.4239, "lon": 78.4400, "route": "v1", "rate": 0.16},
        {"id": "V2", "type": "Passenger", "idx": 0.0, "speed": 52.0, "heading": 270.0, "lat": 17.4239, "lon": 78.4550, "route": "v2", "rate": 0.22},
        {"id": "V3", "type": "Truck",     "idx": 0.0, "speed": 36.0, "heading": 0.0,   "lat": 17.4180, "lon": 78.4483, "route": "v3", "rate": 0.12},
        {"id": "V4", "type": "Emergency", "idx": 0.0, "speed": 75.0, "heading": 180.0, "lat": 17.4290, "lon": 78.4483, "route": "v4", "rate": 0.32},
    ]

    seq_tracker = {v["id"]: 0 for v in vehicles}
    print("[Simulator] 10Hz Multi-Vehicle Telemetry Emitter Active. Press Ctrl+C to stop.")

    try:
        while True:
            timestamp = int(time.time())
            dt = 0.1

            for v in vehicles:
                vid = v["id"]
                seq_tracker[vid] += 1

                # Update position along route or algorithmic trajectory
                if routes and v["route"] in routes:
                    route_pts = routes[v["route"]]
                    v["idx"] += v["rate"]
                    pt_idx = min(len(route_pts) - 1, int(v["idx"]))
                    v["lon"], v["lat"] = route_pts[pt_idx]

                    # Loop around route when reaching end
                    if v["idx"] >= len(route_pts) - 1:
                        v["idx"] = 0.0
                else:
                    heading_rad = math.radians(v["heading"])
                    v["lat"] += (v["speed"] / 3600.0) * dt * math.cos(heading_rad) / 111.0
                    v["lon"] += (v["speed"] / 3600.0) * dt * math.sin(heading_rad) / (111.0 * math.cos(math.radians(v["lat"])))

                # Add realistic road dynamics (slight acceleration jitter and road pitch/roll)
                v["speed"] = max(10.0, min(100.0, v["speed"] + random.uniform(-0.6, 0.6)))
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
                    "fault_code": "NONE"
                }

                # Cryptographically sign packet
                telemetry["signature"] = generate_signature(telemetry)

                # Broadcast to Mosquitto MQTT or Direct-Dispatch
                raw_payload = json.dumps(telemetry)
                if mqtt_active:
                    client.publish(MQTT_TOPIC_TELEMETRY, raw_payload)
                else:
                    publish_or_dispatch(MQTT_TOPIC_TELEMETRY, raw_payload)

            time.sleep(0.1) # 10Hz telemetry stream

    except KeyboardInterrupt:
        print("\n[Simulator] Simulation terminated by user.")
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass

if __name__ == "__main__":
    main()
