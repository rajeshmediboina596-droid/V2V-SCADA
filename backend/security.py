import hmac
import hashlib
import json
import time
from backend.config import HMAC_SECRET, REPLAY_TOLERANCE_SECONDS
from backend.database import log_security_event

# In-memory tracking of sequence numbers per vehicle for replay detection
last_sequence_numbers = {}

def build_signing_string(data: dict) -> str:
    """
    Constructs the canonical string representation for HMAC-SHA256 signing.
    Matches the exact STM32 firmware and simulation serializers:
    vehicle_id + vehicle_type + timestamp + seq + lat + lon + speed_kmph + heading_deg
    """
    vid = str(data.get('vehicle_id', ''))
    vtype = str(data.get('vehicle_type', 'Passenger'))
    ts = str(data.get('timestamp', ''))
    seq = str(data.get('seq', 0))
    lat = f"{float(data.get('lat', 0.0)):.6f}"
    lon = f"{float(data.get('lon', 0.0)):.6f}"
    speed = f"{float(data.get('speed_kmph', 0.0)):.1f}"
    heading = str(int(round(float(data.get('heading_deg', 0.0)))))

    return f"{vid}{vtype}{ts}{seq}{lat}{lon}{speed}{heading}"

def generate_signature(data: dict) -> str:
    """Generates the expected HMAC-SHA256 hex digest for a payload."""
    sign_str = build_signing_string(data)
    return hmac.new(HMAC_SECRET, sign_str.encode('utf-8'), hashlib.sha256).hexdigest()

def verify_telemetry_packet(payload_str: str):
    """
    Validates HMAC-SHA256 signature, timestamp freshness, and sequence numbers.
    Returns:
        (is_valid: bool, data: dict, error_reason: str)
    """
    try:
        data = json.loads(payload_str)
    except Exception as e:
        log_security_event("MALFORMED_JSON", "UNKNOWN", f"JSON parsing failed: {e}", payload_str[:100])
        return False, None, "MALFORMED_JSON"

    msg_sig = data.pop('signature', None)
    if not msg_sig:
        log_security_event("MISSING_SIGNATURE", data.get('vehicle_id', 'UNKNOWN'), "Packet has no signature", payload_str[:100])
        return False, data, "MISSING_SIGNATURE"

    vid = data.get('vehicle_id', 'UNKNOWN')
    now = time.time()
    packet_time = data.get('timestamp', now)

    # 1. Timestamp Freshness Check (Anti-Replay)
    if abs(now - packet_time) > REPLAY_TOLERANCE_SECONDS:
        # Allow demo vehicles to pass timestamp check if simulated
        if not vid.startswith("DEMO-"):
            log_security_event("TIMESTAMP_EXPIRED", vid, f"Timestamp skewed by {abs(now - packet_time):.1f}s", payload_str[:100])
            return False, data, "TIMESTAMP_EXPIRED"

    # 2. Cryptographic Signature Validation
    # Authenticity & integrity must be verified before inspecting message contents/sequence
    sign_str_v2 = build_signing_string(data)
    expected_sig_v2 = hmac.new(HMAC_SECRET, sign_str_v2.encode('utf-8'), hashlib.sha256).hexdigest()

    # Legacy format fallback (without seq)
    legacy_str = f"{data.get('vehicle_id')}{data.get('vehicle_type', 'Passenger')}{data.get('timestamp')}{float(data.get('lat', 0)):.6f}{float(data.get('lon', 0)):.6f}{float(data.get('speed_kmph', 0)):.1f}{int(round(float(data.get('heading_deg', 0))))}"
    expected_sig_legacy = hmac.new(HMAC_SECRET, legacy_str.encode('utf-8'), hashlib.sha256).hexdigest()

    is_valid = hmac.compare_digest(expected_sig_v2, msg_sig) or hmac.compare_digest(expected_sig_legacy, msg_sig)

    if not is_valid:
        log_security_event("HMAC_SIGNATURE_MISMATCH", vid, "Invalid cryptographic signature. Ghost vehicle attack suspected.", payload_str[:100])
        return False, data, "HMAC_SIGNATURE_MISMATCH"

    # 3. Monotonic Sequence Number Check (Anti-Replay for verified packets)
    seq = data.get('seq', 0)
    if vid in last_sequence_numbers:
        prev_seq = last_sequence_numbers[vid]
        # Reject duplicate or backwards sequence unless node rebooted (detected by big timestamp jump)
        if seq <= prev_seq and not vid.startswith("DEMO-") and (now - packet_time < 5):
            log_security_event("REPLAY_SEQUENCE_DUPLICATE", vid, f"Duplicate or backwards sequence #{seq} <= #{prev_seq}", payload_str[:100])
            return False, data, "REPLAY_SEQUENCE_DUPLICATE"

    # Update sequence tracker
    last_sequence_numbers[vid] = seq
    return True, data, None
