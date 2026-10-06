import paho.mqtt.client as mqtt
import json
import asyncio
import math
import time
import os
from typing import Dict, Any, Tuple

from backend.config import (
    MQTT_BROKER, MQTT_PORT, MQTT_TOPIC_TELEMETRY, MQTT_USERNAME, MQTT_PASSWORD, MQTT_USE_TLS,
    MQTT_CA_CERT, MQTT_CLIENT_CERT, MQTT_CLIENT_KEY, MQTT_SECURITY_MODE,
    RESTRICTED_ZONE, TTC_CRITICAL_SECONDS, TTC_WARNING_SECONDS,
    TTC_ADVISORY_SECONDS, EMERGENCY_PROXIMITY_METERS
)

from backend.database import log_telemetry, log_incident, log_security_event
from backend.security import verify_telemetry_packet
from backend.highway_toll import highway_toll_manager, haversine
from ml.collision_model import CollisionPredictor

# In-memory latest state for each active vehicle
vehicle_states: Dict[str, Dict[str, Any]] = {}
gateway_health_state: Dict[str, Any] = {
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
VEHICLE_EXPIRY_SECONDS = 15.0

last_pair_evaluation: Dict[str, float] = {}
last_alert_sent: Dict[str, float] = {}
last_incident_logged: Dict[str, float] = {}
last_telemetry_logged: Dict[str, float] = {}

def _extract_pt(pt) -> Tuple[float, float]:
    if isinstance(pt, dict):
        return float(pt.get("lat", 0.0)), float(pt.get("lon", 0.0))
    return float(pt[0]), float(pt[1])

def is_in_polygon(lat: float, lon: float, poly) -> bool:
    """Ray-casting algorithm to test whether a coordinate is inside a polygon."""
    if not poly:
        return False
    n = len(poly)
    inside = False
    p1x, p1y = _extract_pt(poly[0])
    for i in range(1, n + 1):
        p2x, p2y = _extract_pt(poly[i % n])
        if min(p1y, p2y) < lon <= max(p1y, p2y):
            if lat <= max(p1x, p2x):
                if p1y != p2y:
                    xints = (lon - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or lat <= xints:
                    inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def compute_collision_risk(v1_data: dict, v2_data: dict) -> Tuple[float, float, int, float]:
    """
    Computes 2D relative motion physics between two moving vehicles using
    Haversine geodesic distance and velocity vector projection.
    Returns:
        (distance_m, closing_speed_mps, risk_level, ttc_seconds)
    """
    try:
        lat1 = float(v1_data.get('lat', 0.0))
        lon1 = float(v1_data.get('lon', 0.0))
        lat2 = float(v2_data.get('lat', 0.0))
        lon2 = float(v2_data.get('lon', 0.0))
    except (ValueError, TypeError):
        return 999.0, 0.0, 0, 99.9

    distance = haversine(lat1, lon1, lat2, lon2)

    # Protect against negative speeds and convert to m/s
    s1 = max(0.0, float(v1_data.get('speed_kmph', 0.0))) / 3.6
    s2 = max(0.0, float(v2_data.get('speed_kmph', 0.0))) / 3.6

    # Normalize heading into [0, 360) degrees
    # Compass convention: 0 deg = North (+Y), 90 deg = East (+X), 180 deg = South (-Y), 270 deg = West (-X)
    h1 = math.radians(float(v1_data.get('heading_deg', 0.0)) % 360.0)
    h2 = math.radians(float(v2_data.get('heading_deg', 0.0)) % 360.0)

    v1x = s1 * math.sin(h1)
    v1y = s1 * math.cos(h1)
    v2x = s2 * math.sin(h2)
    v2y = s2 * math.cos(h2)

    # Relative velocity of V1 relative to V2: (v1 - v2)
    rvx = v1x - v2x
    rvy = v1y - v2y

    # Displacement vector pointing from V1 to V2 in local metric Cartesian space
    mid_lat = math.radians((lat1 + lat2) / 2.0)
    dx = (lon2 - lon1) * 111320.0 * math.cos(mid_lat)
    dy = (lat2 - lat1) * 111320.0

    pos_mag = math.sqrt(dx * dx + dy * dy)
    if pos_mag < 0.1:
        pos_mag = 0.1

    # Closing speed is the rate at which separation decreases along line-of-sight: (r_rel . v_rel) / |r_rel|
    dot_product = (dx * rvx + dy * rvy)
    closing_speed = dot_product / pos_mag

    if closing_speed < 0.0:
        closing_speed = 0.0

    # High-Priority Emergency Vehicle Preemption Check (Threat Level 4)
    is_emergency = (
        v1_data.get('vehicle_type') == 'Emergency' or v1_data.get('emergency_status') == 1 or
        v2_data.get('vehicle_type') == 'Emergency' or v2_data.get('emergency_status') == 1
    )

    if is_emergency and distance < EMERGENCY_PROXIMITY_METERS:
        risk_level = 4
    else:
        risk_level = predictor.predict_risk(distance, closing_speed)

    ttc = (distance / closing_speed) if closing_speed > 0.5 else 99.9

    return distance, closing_speed, risk_level, ttc


def _pair_key(vehicle_a: str, vehicle_b: str) -> str:
    return '|'.join(sorted((vehicle_a, vehicle_b)))

def _is_due(registry: dict, key: str, interval: float, now: float) -> bool:
    if now - registry.get(key, 0) < interval:
        return False
    registry[key] = now
    return True

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
        print(f"[MQTT] Connected successfully to Mosquitto Broker (code {rc}) [Security Mode: {MQTT_SECURITY_MODE}]")
        client.subscribe("v2v/telemetry")
        client.subscribe("v2v/gateway/health")
    else:
        is_mqtt_connected = False
        print(f"[MQTT] Connection returned error code: {rc}")

def on_disconnect(client, userdata, rc):
    global is_mqtt_connected
    is_mqtt_connected = False
    if rc != 0:
        print(f"[MQTT] Unexpected disconnection (rc={rc}). Reconnecting in background...")

def process_telemetry_payload(payload_str: str, client=None, loop=None):
    """
    Ingests, cryptographically verifies, evaluates collision physics,
    and dispatches a vehicle telemetry packet.
    """
    t_start = time.perf_counter()
    from backend.metrics import metrics
    metrics.inc_ingested()

    if loop is None:
        loop = server_event_loop
    if client is None:
        client = mqtt_client_instance

    is_valid, data, reason = verify_telemetry_packet(payload_str)
    if not is_valid:
        metrics.inc_rejected()
        source_id = data.get('vehicle_id', 'UNKNOWN') if data else 'UNKNOWN'
        print(f"[SECURITY ALERT] Dropping invalid packet from {source_id} (Reason: {reason})")
        log_security_event("HMAC_SIGNATURE_DROP", source_id, f"Invalid packet rejected: {reason}", payload_str[:120])
        metrics.telemetry_pipeline.record((time.perf_counter() - t_start) * 1000.0)
        return

    vid = data['vehicle_id']
    now = time.time()
    vehicle_states[vid] = data
    data['last_seen'] = now

    # Periodically prune stale vehicles that have stopped broadcasting for > 15s
    stale_vids = [v for v, state in vehicle_states.items() if (now - state.get('last_seen', now)) > VEHICLE_EXPIRY_SECONDS]
    for stale_vid in stale_vids:
        del vehicle_states[stale_vid]

    # Database logging at throttled interval
    if _is_due(last_telemetry_logged, vid, TELEMETRY_LOG_INTERVAL_SECONDS, now):
        log_telemetry(data)

    alarms = []

    # 1. Geofence Boundary Check
    if is_in_polygon(data['lat'], data['lon'], RESTRICTED_ZONE):
        alert = {
            "type": "geofence_violation",
            "vehicle_a": vid,
            "vehicle_b": "GEOFENCE",
            "risk_level": 3,
            "message": f"CRITICAL: {vid} has breached restricted highway work zone!"
        }
        _emit_alert(client, alarms, alert, now)

    # 2. Highway Tollgate Proximity & Crossing Assessment
    toll_events, route_info = highway_toll_manager.evaluate_vehicle(data)
    for evt in toll_events:
        alarms.append(evt)

    # 3. Multi-Vehicle Peer Collision Risk Assessment
    for other_id, other_data in list(vehicle_states.items()):
        if other_id == vid:
            continue

        pair = _pair_key(vid, other_id)
        if not _is_due(last_pair_evaluation, pair, PAIR_EVALUATION_INTERVAL_SECONDS, now):
            continue

        c_start = time.perf_counter()
        distance, closing_speed, risk_level, ttc = compute_collision_risk(data, other_data)
        metrics.collision_physics.record((time.perf_counter() - c_start) * 1000.0)
        metrics.inc_collision_checks()

        # Check for High-Priority Emergency Vehicle Proximity Preemption
        is_emergency = (data.get('vehicle_type') == 'Emergency' or data.get('emergency_status') == 1 or
                        other_data.get('vehicle_type') == 'Emergency' or other_data.get('emergency_status') == 1)

        if is_emergency and distance < EMERGENCY_PROXIMITY_METERS:
            em_id = vid if data.get('vehicle_type') == 'Emergency' else other_id
            civ_id = other_id if em_id == vid else vid
            alert = {
                "type": "emergency_vehicle_proximity",
                "vehicle_a": civ_id,
                "vehicle_b": em_id,
                "distance": round(distance, 1),
                "risk_level": 4,
                "message": f"EMERGENCY VEHICLE YIELD: Ambulance/Police {em_id} within {int(distance)}m! Move left."
            }
            _emit_alert(client, alarms, alert, now)

        # Evaluate Standard Collision Risk Thresholds
        if risk_level > 0 and distance < 120.0:
            if _is_due(last_incident_logged, pair, INCIDENT_LOG_INTERVAL_SECONDS, now):
                log_incident(vid, other_id, distance, closing_speed, risk_level, ttc)

            msg = "COLLISION ALERT: Potential hazard ahead."
            if risk_level == 2:
                msg = f"CRITICAL IMMINENT COLLISION! TTC {ttc:.1f}s | Dist: {distance:.1f}m. Emergency Braking."
            elif risk_level == 1:
                msg = f"WARNING: Approaching {other_id} rapidly (TTC {ttc:.1f}s)."

            alert = {
                "type": "collision_warning",
                "vehicle_a": vid,
                "vehicle_b": other_id,
                "distance": round(distance, 1),
                "closing_speed": round(closing_speed, 1),
                "ttc_seconds": round(ttc, 1),
                "risk_level": risk_level,
                "message": msg
            }
            _emit_alert(client, alarms, alert, now)

    # 4. Dispatch Telemetry Update to Active SCADA WebSocket Clients
    if loop:
        event = {
            "type": "telemetry",
            "data": data,
            "alarms": alarms,
            "route_info": route_info
        }
        asyncio.run_coroutine_threadsafe(message_queue.put(event), loop)

    metrics.telemetry_pipeline.record((time.perf_counter() - t_start) * 1000.0)

def publish_or_dispatch(topic: str, payload_str: str):
    """
    Publishes to MQTT broker if connected; otherwise processes immediately in-memory.
    Guarantees seamless zero-broker offline demo operation.
    """
    if mqtt_client_instance and is_mqtt_connected:
        try:
            mqtt_client_instance.publish(topic, payload_str)
            return
        except Exception:
            pass

    if topic == MQTT_TOPIC_TELEMETRY:
        process_telemetry_payload(payload_str, client=None, loop=server_event_loop)
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

def on_message(client, userdata, msg):
    topic = msg.topic
    payload_str = msg.payload.decode('utf-8', errors='ignore')
    loop = userdata.get('loop') if userdata else server_event_loop

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

    if topic == "v2v/telemetry":
        process_telemetry_payload(payload_str, client=client, loop=loop)

def start_mqtt_client(loop):
    global server_event_loop, mqtt_client_instance
    server_event_loop = loop
    client = mqtt.Client(client_id="V2V_SCADA_Backend", userdata={'loop': loop})
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    mqtt_client_instance = client

    # Apply Authentication in Secure Mode or when credentials provided
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    # Apply TLS in Secure Mode
    if MQTT_USE_TLS and MQTT_CA_CERT and os.path.exists(MQTT_CA_CERT):
        try:
            client.tls_set(
                ca_certs=MQTT_CA_CERT,
                certfile=MQTT_CLIENT_CERT if os.path.exists(MQTT_CLIENT_CERT) else None,
                keyfile=MQTT_CLIENT_KEY if os.path.exists(MQTT_CLIENT_KEY) else None
            )
            print("[MQTT] TLS encryption configured for secure transport.")
        except Exception as e:
            print(f"[MQTT] TLS Configuration Warning: {e}")

    try:
        client.connect_async(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        print(f"[MQTT] Connection Notice: {e}. Operating in autonomous direct-dispatch mode.")
