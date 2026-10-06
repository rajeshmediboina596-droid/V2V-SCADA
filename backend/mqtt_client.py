import paho.mqtt.client as mqtt
import json
import asyncio
import math
import time
from backend.config import MQTT_BROKER, MQTT_PORT, RESTRICTED_ZONE
from backend.database import log_telemetry, log_incident, log_security_event
from backend.security import verify_telemetry_packet
from backend.highway_toll import highway_toll_manager, haversine
from ml.collision_model import CollisionPredictor

# In-memory latest state for each active vehicle
vehicle_states = {}
gateway_health_state = {
    "status": "Online",
    "port": "COM3",
    "packets_rx": 0,
    "last_seen": time.time()
}

# Event queue for WebSockets
message_queue = asyncio.Queue()
predictor = CollisionPredictor()

PAIR_EVALUATION_INTERVAL_SECONDS = 0.2
ALERT_RESEND_INTERVAL_SECONDS = 1.0
INCIDENT_LOG_INTERVAL_SECONDS = 4.0
TELEMETRY_LOG_INTERVAL_SECONDS = 0.5

last_pair_evaluation = {}
last_alert_sent = {}
last_incident_logged = {}
last_telemetry_logged = {}

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

def compute_collision_risk(v1_data, v2_data):
    distance = haversine(v1_data['lat'], v1_data['lon'], v2_data['lat'], v2_data['lon'])

    s1 = v1_data['speed_kmph'] / 3.6
    s2 = v2_data['speed_kmph'] / 3.6

    # Compass heading: 0 deg = North (+Y), 90 deg = East (+X), 180 deg = South (-Y), 270 deg = West (-X)
    h1 = math.radians(v1_data['heading_deg'])
    h2 = math.radians(v2_data['heading_deg'])

    v1x = s1 * math.sin(h1)
    v1y = s1 * math.cos(h1)
    v2x = s2 * math.sin(h2)
    v2y = s2 * math.cos(h2)

    # Relative velocity of V1 relative to V2: (v1 - v2)
    rvx = v1x - v2x
    rvy = v1y - v2y

    # Displacement vector pointing from V1 to V2
    mid_lat = math.radians((v1_data['lat'] + v2_data['lat']) / 2.0)
    dx = (v2_data['lon'] - v1_data['lon']) * 111320.0 * math.cos(mid_lat)
    dy = (v2_data['lat'] - v1_data['lat']) * 111320.0

    pos_mag = math.sqrt(dx * dx + dy * dy)
    if pos_mag < 0.1:
        pos_mag = 0.1

    # Closing speed is rate at which distance decreases: (v1 - v2) . (r2 - r1) / |r2 - r1|
    dot_product = (dx * rvx + dy * rvy)
    closing_speed = dot_product / pos_mag

    if closing_speed < 0:
        closing_speed = 0.0

    risk_level = predictor.predict_risk(distance, closing_speed)
    ttc = (distance / closing_speed) if closing_speed > 0.5 else 99.9
    return distance, closing_speed, risk_level, ttc

def _pair_key(vehicle_a, vehicle_b):
    return '|'.join(sorted((vehicle_a, vehicle_b)))

def _is_due(registry, key, interval, now):
    if now - registry.get(key, 0) < interval:
        return False
    registry[key] = now
    return True

# Global runtime state for event loop and MQTT instance
server_event_loop = None
mqtt_client_instance = None
is_mqtt_connected = False

def _emit_alert(client, alarms, alert, now):
    pair = _pair_key(alert['vehicle_a'], alert['vehicle_b'])
    key = f"{alert['risk_level']}|{pair}"
    if not _is_due(last_alert_sent, key, ALERT_RESEND_INTERVAL_SECONDS, now):
        return
    alarms.append(alert)
    if client and hasattr(client, 'publish') and is_mqtt_connected:
        try:
            client.publish(f"v2v/alerts/{alert['vehicle_a']}", json.dumps(alert))
            if alert['vehicle_b'] not in ('GEOFENCE', alert['vehicle_a']):
                client.publish(f"v2v/alerts/{alert['vehicle_b']}", json.dumps(alert))
        except Exception:
            pass

def on_connect(client, userdata, flags, rc):
    global is_mqtt_connected
    if rc == 0:
        is_mqtt_connected = True
        print(f"[MQTT] Connected successfully to Mosquitto (code {rc})")
        client.subscribe("v2v/telemetry")
        client.subscribe("v2v/gateway/health")

def process_telemetry_payload(payload_str, client=None, loop=None):
    """
    Ingests and processes a raw telemetry JSON packet.
    Performs cryptographic validation, geofencing, tollgate monitoring,
    collision prediction, database logging, and WebSocket dispatch.
    """
    if loop is None:
        loop = server_event_loop
    if client is None:
        client = mqtt_client_instance

    is_valid, data, reason = verify_telemetry_packet(payload_str)
    if not is_valid:
        source_id = data.get('vehicle_id', 'UNKNOWN') if data else 'UNKNOWN'
        print(f"[SECURITY ALERT] Dropping invalid packet from {source_id} (Reason: {reason})")
        log_security_event("HMAC_SIGNATURE_DROP", source_id, f"Invalid packet rejected: {reason}", payload_str)
        if loop:
            evt = {
                "type": "security_alert",
                "reason": reason,
                "payload": payload_str,
                "source_id": source_id
            }
            asyncio.run_coroutine_threadsafe(message_queue.put(evt), loop)
        return False, data, reason

    vid = data['vehicle_id']
    now = time.monotonic()

    # Rate-limited database logging
    if _is_due(last_telemetry_logged, vid, TELEMETRY_LOG_INTERVAL_SECONDS, now):
        log_telemetry(data)

    alarms = []

    # 1. Geofence Evaluation
    if is_in_polygon(data['lat'], data['lon'], RESTRICTED_ZONE):
        alert = {
            "vehicle_a": vid,
            "vehicle_b": "GEOFENCE",
            "distance": 0,
            "closing_speed": data.get('speed_kmph', 0.0),
            "risk_level": 3,
            "ttc": 0.0
        }
        _emit_alert(client, alarms, alert, now)

    # 2. Highway Tollgate Evaluation (Approach & Crossing)
    toll_events, route_info = highway_toll_manager.evaluate_vehicle(data)

    # 3. Inter-Vehicle Collision & Emergency Physics
    is_demo_vid = vid.startswith("DEMO-")

    for other_vid, other_data in list(vehicle_states.items()):
        if other_vid != vid:
            # Segregate demo and live hardware physics
            if is_demo_vid != other_vid.startswith("DEMO-"):
                continue

            pair = _pair_key(vid, other_vid)
            if not _is_due(last_pair_evaluation, pair, PAIR_EVALUATION_INTERVAL_SECONDS, now):
                continue

            dist, closing_speed, risk, ttc = compute_collision_risk(data, other_data)

            # Emergency Vehicle Proximity Alert (< 200m)
            v_type = data.get('vehicle_type', 'Passenger')
            other_v_type = other_data.get('vehicle_type', 'Passenger')

            if dist < 200.0:
                if v_type == 'Emergency' or other_v_type == 'Emergency':
                    em_alert = {
                        "vehicle_a": vid,
                        "vehicle_b": other_vid,
                        "distance": round(dist, 1),
                        "closing_speed": round(closing_speed, 1),
                        "risk_level": 4, # 4 = Emergency Vehicle Yield
                        "ttc": round(ttc, 1)
                    }
                    _emit_alert(client, alarms, em_alert, now)

            # Imminent / Potential Collision
            if risk > 0:
                alert = {
                    "vehicle_a": vid,
                    "vehicle_b": other_vid,
                    "distance": round(dist, 1),
                    "closing_speed": round(closing_speed, 1),
                    "risk_level": int(risk),
                    "ttc": round(ttc, 1)
                }
                _emit_alert(client, alarms, alert, now)

                incident_key = f"{risk}|{pair}"
                if _is_due(last_incident_logged, incident_key, INCIDENT_LOG_INTERVAL_SECONDS, now):
                    log_incident(vid, other_vid, dist, closing_speed, risk, ttc)

    # Store latest state in memory
    vehicle_states[vid] = data

    # Dispatch to SCADA Frontend via WebSocket queue
    if loop:
        evt = {
            "type": "telemetry",
            "data": data,
            "alarms": alarms,
            "route_info": route_info,
            "toll_events": toll_events
        }
        asyncio.run_coroutine_threadsafe(message_queue.put(evt), loop)

    return True, data, "OK"

def publish_or_dispatch(topic, payload_str):
    """
    Publishes to MQTT broker if connected; also processes directly
    in-process so simulation, spoof testing, and telemetry work without
    requiring an external MQTT daemon.
    """
    global mqtt_client_instance, server_event_loop

    if mqtt_client_instance and is_mqtt_connected:
        try:
            mqtt_client_instance.publish(topic, payload_str)
        except Exception:
            pass

    if topic == "v2v/telemetry":
        process_telemetry_payload(payload_str, client=mqtt_client_instance, loop=server_event_loop)
    elif topic == "v2v/gateway/health":
        try:
            gw_data = json.loads(payload_str)
            gateway_health_state.update(gw_data)
            gateway_health_state["last_seen"] = time.time()
            if server_event_loop:
                evt = {"type": "gateway_health", "data": gateway_health_state}
                asyncio.run_coroutine_threadsafe(message_queue.put(evt), server_event_loop)
        except Exception:
            pass
    elif topic == "v2v/commands":
        try:
            cmd_data = json.loads(payload_str)
            if server_event_loop:
                evt = {"type": "command_broadcast", "data": cmd_data}
                asyncio.run_coroutine_threadsafe(message_queue.put(evt), server_event_loop)
        except Exception:
            pass

def on_message(client, userdata, msg):
    topic = msg.topic
    payload_str = msg.payload.decode('utf-8', errors='ignore')
    loop = userdata.get('loop') if userdata else server_event_loop

    # Handle Gateway Node Health Heartbeat
    if topic == "v2v/gateway/health":
        try:
            gw_data = json.loads(payload_str)
            gateway_health_state.update(gw_data)
            gateway_health_state["last_seen"] = time.time()
            if loop:
                evt = {"type": "gateway_health", "data": gateway_health_state}
                asyncio.run_coroutine_threadsafe(message_queue.put(evt), loop)
        except Exception:
            pass
        return

    # Handle Vehicle Telemetry
    if topic == "v2v/telemetry":
        process_telemetry_payload(payload_str, client=client, loop=loop)

def start_mqtt_client(loop):
    global server_event_loop, mqtt_client_instance
    server_event_loop = loop
    client = mqtt.Client(client_id="V2V_SCADA_Backend", userdata={'loop': loop})
    client.on_connect = on_connect
    client.on_message = on_message
    mqtt_client_instance = client

    try:
        client.connect_async(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        print(f"[MQTT] Connection Notice (Local Broker Offline): {e}. Operating in autonomous direct-dispatch mode.")

