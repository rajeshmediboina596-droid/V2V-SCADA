import paho.mqtt.client as mqtt
import json
import hmac
import hashlib
import asyncio
from backend.database import log_telemetry, log_incident
from ml.collision_model import CollisionPredictor
import math
import ssl

SECRET_KEY = b"v2v_shared_secret_123"

# In-memory latest state for each vehicle
vehicle_states = {}
# Event queue for WebSockets
message_queue = asyncio.Queue()
predictor = CollisionPredictor()

RESTRICTED_ZONE = [
    (17.4245, 78.4460),
    (17.4245, 78.4530),
    (17.4190, 78.4530),
    (17.4190, 78.4460)
]

def is_in_polygon(lat, lon, poly):
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]
    for i in range(1, n + 1):
        p2x, p2y = poly[i % n]
        if min(p1y, p2y) < lon <= max(p1y, p2y):
            if lat <= max(p1x, p2x):
                if p1y != p2y:
                    xints = (lon - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or lat <= xints:
                    inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def verify_signature(payload_str):
    try:
        data = json.loads(payload_str)
        msg_sig = data.pop('signature', None)
        if not msg_sig:
            return False, None
        
        # recreate string to sign
        v_type = data.get('vehicle_type', 'Passenger')
        sign_str = f"{data['vehicle_id']}{v_type}{data['timestamp']}{data['lat']}{data['lon']}{data['speed_kmph']}{data['heading_deg']}"
        expected_sig = hmac.new(SECRET_KEY, sign_str.encode(), hashlib.sha256).hexdigest()
        
        is_valid = hmac.compare_digest(expected_sig, msg_sig)
        return is_valid, data
    except Exception as e:
        print(f"Signature verify error: {e}")
        return False, None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000 # radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def compute_collision_risk(v1_data, v2_data):
    distance = haversine(v1_data['lat'], v1_data['lon'], v2_data['lat'], v2_data['lon'])
    
    s1 = v1_data['speed_kmph'] / 3.6
    s2 = v2_data['speed_kmph'] / 3.6
    
    h1 = math.radians(v1_data['heading_deg'])
    h2 = math.radians(v2_data['heading_deg'])
    
    v1x = s1 * math.cos(h1)
    v1y = s1 * math.sin(h1)
    v2x = s2 * math.cos(h2)
    v2y = s2 * math.sin(h2)
    
    rvx = v1x - v2x
    rvy = v1y - v2y
    
    dx = (v1_data['lon'] - v2_data['lon']) * 111320 * math.cos(math.radians((v1_data['lat'] + v2_data['lat'])/2))
    dy = (v1_data['lat'] - v2_data['lat']) * 111320
    
    pos_mag = math.sqrt(dx*dx + dy*dy)
    if pos_mag == 0: pos_mag = 0.001
    
    dot_product = (dx * rvx + dy * rvy)
    closing_speed = - (dot_product / pos_mag)
    
    if closing_speed < 0:
        closing_speed = 0
        
    risk_level = predictor.predict_risk(distance, closing_speed)
    return distance, closing_speed, risk_level

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT with result code {rc}")
    client.subscribe("v2v/telemetry")

def on_message(client, userdata, msg):
    payload_str = msg.payload.decode('utf-8')
    
    is_valid, data = verify_signature(payload_str)
    if not is_valid:
        print(f"Invalid signature, dropping message: {payload_str}")
        loop = userdata.get('loop')
        if loop:
            evt = {
                "type": "security_alert",
                "payload": payload_str
            }
            asyncio.run_coroutine_threadsafe(message_queue.put(evt), loop)
        return
        
    vid = data['vehicle_id']
    log_telemetry(data)
    
    alarms = []
    
    # Check Geofence
    if is_in_polygon(data['lat'], data['lon'], RESTRICTED_ZONE):
        alert = {
            "vehicle_a": vid,
            "vehicle_b": "GEOFENCE",
            "distance": 0,
            "closing_speed": data['speed_kmph'],
            "risk_level": 3 # Custom high risk for geofence
        }
        alarms.append(alert)
        client.publish(f"v2v/alerts/{vid}", json.dumps(alert))
    
    is_demo_vid = vid.startswith("DEMO-")
    
    for other_vid, other_data in vehicle_states.items():
        if other_vid != vid:
            # Segregate Demo and Live physics
            other_is_demo = other_vid.startswith("DEMO-")
            if is_demo_vid != other_is_demo:
                continue
                
            dist, closing_speed, risk = compute_collision_risk(data, other_data)
            
            # Emergency Vehicle Override
            v_type = data.get('vehicle_type', 'Passenger')
            other_v_type = other_data.get('vehicle_type', 'Passenger')
            
            if dist < 200: # 200m warning radius for emergency vehicles
                if v_type == 'Emergency' or other_v_type == 'Emergency':
                    em_alert = {
                        "vehicle_a": vid,
                        "vehicle_b": other_vid,
                        "distance": round(dist, 2),
                        "closing_speed": round(closing_speed, 2),
                        "risk_level": 4 # 4 = Emergency Yield
                    }
                    alarms.append(em_alert)
                    client.publish(f"v2v/alerts/{vid}", json.dumps(em_alert))
                    client.publish(f"v2v/alerts/{other_vid}", json.dumps(em_alert))

            if risk > 0:
                alert = {
                    "vehicle_a": vid,
                    "vehicle_b": other_vid,
                    "distance": round(dist, 2),
                    "closing_speed": round(closing_speed, 2),
                    "risk_level": int(risk)
                }
                alarms.append(alert)
                log_incident(vid, other_vid, dist, closing_speed, risk)
                
                # Bi-directional transfer: Send threat data back to physical vehicles
                client.publish(f"v2v/alerts/{vid}", json.dumps(alert))
                client.publish(f"v2v/alerts/{other_vid}", json.dumps(alert))
    
    vehicle_states[vid] = data
    
    loop = userdata.get('loop')
    if loop:
        evt = {
            "type": "telemetry",
            "data": data,
            "alarms": alarms
        }
        asyncio.run_coroutine_threadsafe(message_queue.put(evt), loop)

def start_mqtt_client(loop):
    client = mqtt.Client(userdata={'loop': loop})
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Note: For strict TLS verification, we would configure tls_set here.
    # Since we use self-signed or no cert for local testing depending on user environment,
    # we connect to standard 1883 for now. TLS can be enabled by uncommenting below:
    # client.tls_set(ca_certs="../mqtt/certs/ca.crt", tls_version=ssl.PROTOCOL_TLSv1_2)
    # client.tls_insecure_set(True) 
    
    try:
        client.connect_async("localhost", 1883, 60)
        client.loop_start()
    except Exception as e:
        print(f"Failed to connect to MQTT: {e}")
