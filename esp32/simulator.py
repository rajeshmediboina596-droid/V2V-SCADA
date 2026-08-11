import paho.mqtt.client as mqtt
import time
import json
import hmac
import hashlib

SECRET_KEY = b"v2v_shared_secret_123"

def sign_payload(data):
    sign_str = f"{data['vehicle_id']}{data['vehicle_type']}{data['timestamp']}{data['lat']}{data['lon']}{data['speed_kmph']}{data['heading_deg']}"
    return hmac.new(SECRET_KEY, sign_str.encode(), hashlib.sha256).hexdigest()

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())
        if topic.startswith("v2v/alerts/"):
            my_vid = topic.split('/')[-1]
            threat_vid = payload['vehicle_a'] if payload['vehicle_b'] == my_vid else payload['vehicle_b']
            print(f"\n[!] CRITICAL ALERT RECEIVED for {my_vid}:")
            print(f"    Threat from {threat_vid}! Distance: {payload['distance']}m, Risk Level: {payload['risk_level']}")
            print("    ENGAGING AUTOMATIC EMERGENCY BRAKING (AEB)...\n")
        elif topic == "v2v/commands":
            print(f"\n[Broadcast Command] {payload['cmd']}\n")
    except Exception as e:
        pass

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883, 60)
for vid in ["V1", "V2", "V3", "V4"]:
    client.subscribe(f"v2v/alerts/{vid}")
client.subscribe("v2v/commands")
client.loop_start()

# Load OSRM routes for road-snapping
import os
try:
    with open(os.path.join(os.path.dirname(__file__), '../backend/routes.json'), 'r') as f:
        routes = json.load(f)
except Exception as e:
    print(f"OSRM routes not found: {e}")
    routes = None

v1 = {"idx": 0.0, "speed": 40, "heading": 90, "type": "Passenger"}
v2 = {"idx": 0.0, "speed": 45, "heading": 270, "type": "Passenger"}
v3 = {"idx": 0.0, "speed": 35, "heading": 0, "type": "Passenger"}
v4 = {"idx": 0.0, "speed": 60, "heading": 180, "type": "Emergency"}

v1.update({"lat": 17.4239, "lon": 78.4400})
v2.update({"lat": 17.4239, "lon": 78.4550})
v3.update({"lat": 17.4180, "lon": 78.4483})
v4.update({"lat": 17.4290, "lon": 78.4483})

try:
    print("Starting 4-Vehicle simulation... Press Ctrl+C to stop.")
    while True:
        timestamp = int(time.time())
        dt = 0.1
        
        if routes:
            v1['idx'] += 0.15 
            v2['idx'] += 0.20 
            v3['idx'] += 0.12 
            v4['idx'] += 0.30
            
            v1['lon'], v1['lat'] = routes['v1'][min(len(routes['v1'])-1, int(v1['idx']))]
            v2['lon'], v2['lat'] = routes['v2'][min(len(routes['v2'])-1, int(v2['idx']))]
            v3['lon'], v3['lat'] = routes['v3'][min(len(routes['v3'])-1, int(v3['idx']))]
            v4['lon'], v4['lat'] = routes['v4'][min(len(routes['v4'])-1, int(v4['idx']))]
        else:
            v1['lon'] += (v1['speed'] / 3600.0) * dt / 104.0
            v2['lon'] -= (v2['speed'] / 3600.0) * dt / 104.0
            v3['lat'] += (v3['speed'] / 3600.0) * dt / 111.0
            v4['lat'] -= (v4['speed'] / 3600.0) * dt / 111.0
        
        import random
        for v in [v1, v2, v3, v4]:
            v['speed'] = max(0, v['speed'] + random.uniform(-0.5, 0.5))
        
        for idx, v in enumerate([v1, v2, v3, v4]):
            vid = f"V{idx+1}"
            data = {
                "vehicle_id": vid,
                "vehicle_type": v['type'],
                "timestamp": timestamp,
                "lat": round(v['lat'], 6),
                "lon": round(v['lon'], 6),
                "speed_kmph": round(v['speed'], 1),
                "heading_deg": v['heading']
            }
            data['signature'] = sign_payload(data)
            
            client.publish("v2v/telemetry", json.dumps(data))
            
        print(f"Published 10Hz telemetry for V1, V2, V3, V4 at {timestamp}")
        time.sleep(0.1) # 10Hz telemetry
except KeyboardInterrupt:
    print("Simulation stopped.")
