import hmac
import hashlib
import json
import time
from collections import OrderedDict
from typing import Tuple, Optional, Dict, Any, Union


from backend.config import (
    HMAC_SECRET,
    REPLAY_TOLERANCE_SECONDS,
    MAX_TRACKED_VEHICLES,
    DEMO_MODE,
)
from backend.database import log_security_event

# Bounded in-memory sequence tracking with LRU eviction to prevent memory exhaustion attacks
# Structure: vehicle_id -> {"seq": int, "last_timestamp": float}
_sequence_tracker: OrderedDict[str, Dict[str, Any]] = OrderedDict()

def build_canonical_signing_string(data: dict) -> str:
    """
    Constructs the deterministic key-value canonical representation for HMAC-SHA256 signing.
    Matches the STM32 firmware and Python simulation serializers:
    vehicle_id=...|vehicle_type=...|timestamp=...|seq=...|lat=...|lon=...|speed_kmph=...|heading_deg=...
    """
    vid = str(data.get("vehicle_id", "")).strip()
    vtype = str(data.get("vehicle_type", "Passenger")).strip()
    ts = str(data.get("timestamp", 0))
    seq = str(data.get("seq", 0))

    try:
        lat = f"{float(data.get('lat', 0.0)):.6f}"
    except (ValueError, TypeError):
        lat = "0.000000"

    try:
        lon = f"{float(data.get('lon', 0.0)):.6f}"
    except (ValueError, TypeError):
        lon = "0.000000"

    try:
        speed = f"{float(data.get('speed_kmph', 0.0)):.1f}"
    except (ValueError, TypeError):
        speed = "0.0"

    try:
        heading = str(int(round(float(data.get("heading_deg", 0.0)))))
    except (ValueError, TypeError):
        heading = "0"

    return (
        f"vehicle_id={vid}|vehicle_type={vtype}|timestamp={ts}|seq={seq}|"
        f"lat={lat}|lon={lon}|speed_kmph={speed}|heading_deg={heading}"
    )

def build_legacy_signing_string(data: dict) -> str:
    """Legacy string concatenation fallback for transition compatibility."""
    vid = str(data.get("vehicle_id", ""))
    vtype = str(data.get("vehicle_type", "Passenger"))
    ts = str(data.get("timestamp", ""))
    seq = str(data.get("seq", 0))
    try:
        lat = f"{float(data.get('lat', 0.0)):.6f}"
        lon = f"{float(data.get('lon', 0.0)):.6f}"
        speed = f"{float(data.get('speed_kmph', 0.0)):.1f}"
        heading = str(int(round(float(data.get("heading_deg", 0.0)))))
    except (ValueError, TypeError):
        lat, lon, speed, heading = "0.000000", "0.000000", "0.0", "0"

    return f"{vid}{vtype}{ts}{seq}{lat}{lon}{speed}{heading}"

def generate_signature(data: dict, use_canonical: bool = True) -> str:
    """
    Generates HMAC-SHA256 hex digest for a telemetry payload using the shared secret.
    """
    sign_str = build_canonical_signing_string(data) if use_canonical else build_legacy_signing_string(data)
    return hmac.new(HMAC_SECRET, sign_str.encode("utf-8"), hashlib.sha256).hexdigest()

def _record_sequence(vid: str, seq: int, packet_time: float) -> None:
    """Records sequence number with LRU eviction to prevent memory leaks."""
    if vid in _sequence_tracker:
        _sequence_tracker.move_to_end(vid)
    elif len(_sequence_tracker) >= MAX_TRACKED_VEHICLES:
        _sequence_tracker.popitem(last=False)  # Evict oldest tracked vehicle
    _sequence_tracker[vid] = {"seq": seq, "last_timestamp": packet_time}


def reset_vehicle_sequence(vid: str) -> None:
    """Resets tracked sequence number for a given vehicle (useful for reboots and tests)."""
    _sequence_tracker.pop(vid, None)


def clear_sequence_tracker() -> None:
    """Clears all tracked vehicle sequences."""
    _sequence_tracker.clear()


def verify_telemetry_packet(
    payload: Union[str, Dict[str, Any]],
    strict: bool = False
) -> Tuple[bool, Optional[dict], Optional[str]]:
    """
    Validates HMAC-SHA256 signature, timestamp freshness, and monotonic sequence numbers.
    Accepts either a JSON string or parsed dictionary.
    
    Args:
        payload: Serialized JSON packet string or Python dictionary.
        strict: If True, enforces strict timestamp and sequence checks even in demo mode.
        
    Returns:
        (is_valid: bool, data: dict or None, error_reason: str)
    """
    if isinstance(payload, dict):
        data = dict(payload)
        payload_str = json.dumps(payload)
    elif isinstance(payload, str):
        payload_str = payload
        try:
            data = json.loads(payload_str)
        except Exception as e:
            log_security_event("MALFORMED_JSON", "UNKNOWN", f"JSON parsing failed: {e}", payload_str[:100])
            return False, None, "MALFORMED_JSON"
    else:
        log_security_event("INVALID_PAYLOAD_TYPE", "UNKNOWN", "Payload must be JSON string or dict", str(payload)[:100])
        return False, None, "INVALID_PAYLOAD_TYPE"

    if not isinstance(data, dict):
        log_security_event("INVALID_PAYLOAD_TYPE", "UNKNOWN", "Payload must be a JSON object", payload_str[:100])
        return False, None, "INVALID_PAYLOAD_TYPE"

    msg_sig = data.pop("signature", None)
    if not msg_sig:
        vid = data.get("vehicle_id", "UNKNOWN")
        log_security_event("MISSING_SIGNATURE", vid, "Packet missing HMAC signature", payload_str[:100])
        return False, data, "MISSING_SIGNATURE"

    vid = str(data.get("vehicle_id", "UNKNOWN")).strip()
    now = time.time()

    # 1. Type & Range Validation for Security Fields
    try:
        packet_time = float(data.get("timestamp", now))
    except (ValueError, TypeError):
        log_security_event("INVALID_TIMESTAMP_TYPE", vid, "Timestamp is not a valid number", payload_str[:100])
        return False, data, "INVALID_TIMESTAMP_TYPE"

    try:
        seq = int(data.get("seq", 0))
        if seq < 0:
            log_security_event("NEGATIVE_SEQUENCE", vid, f"Sequence number cannot be negative: {seq}", payload_str[:100])
            return False, data, "NEGATIVE_SEQUENCE"
    except (ValueError, TypeError):
        log_security_event("INVALID_SEQUENCE_TYPE", vid, "Sequence number must be an integer", payload_str[:100])
        return False, data, "INVALID_SEQUENCE_TYPE"

    # 2. Timestamp Freshness Check (Anti-Replay)
    time_skew = abs(now - packet_time)
    if time_skew > REPLAY_TOLERANCE_SECONDS:
        # In demo mode, relaxed tolerance for recorded/simulated replays unless strict=True
        if strict or not DEMO_MODE:
            log_security_event(
                "TIMESTAMP_EXPIRED",
                vid,
                f"Timestamp skewed by {time_skew:.1f}s (Tolerance: {REPLAY_TOLERANCE_SECONDS}s)",
                payload_str[:100],
            )
            return False, data, "TIMESTAMP_EXPIRED"

    # 3. Cryptographic Signature Validation
    # Test canonical format first, then legacy format
    canonical_str = build_canonical_signing_string(data)
    expected_canonical_sig = hmac.new(HMAC_SECRET, canonical_str.encode("utf-8"), hashlib.sha256).hexdigest()

    legacy_str = build_legacy_signing_string(data)
    expected_legacy_sig = hmac.new(HMAC_SECRET, legacy_str.encode("utf-8"), hashlib.sha256).hexdigest()

    # Legacy without seq fallback
    legacy_no_seq = f"{data.get('vehicle_id')}{data.get('vehicle_type', 'Passenger')}{data.get('timestamp')}{float(data.get('lat', 0)):.6f}{float(data.get('lon', 0)):.6f}{float(data.get('speed_kmph', 0)):.1f}{int(round(float(data.get('heading_deg', 0))))}"
    expected_no_seq_sig = hmac.new(HMAC_SECRET, legacy_no_seq.encode("utf-8"), hashlib.sha256).hexdigest()

    is_valid = (
        hmac.compare_digest(expected_canonical_sig, msg_sig)
        or hmac.compare_digest(expected_legacy_sig, msg_sig)
        or hmac.compare_digest(expected_no_seq_sig, msg_sig)
    )

    if not is_valid:
        log_security_event(
            "HMAC_SIGNATURE_MISMATCH",
            vid,
            "Invalid cryptographic signature. Unauthorized injection or payload tampering detected.",
            payload_str[:100],
        )
        return False, data, "HMAC_SIGNATURE_MISMATCH"

    # 4. Monotonic Sequence Number Check (Anti-Replay)
    if vid in _sequence_tracker:
        last_info = _sequence_tracker[vid]
        prev_seq = last_info["seq"]
        prev_time = last_info["last_timestamp"]

        # Detect node reboot: if seq dropped back to start (<= 5) and time advanced, accept as reboot
        is_node_reboot = (seq <= 5 and prev_seq > 10 and (packet_time >= prev_time))

        if seq <= prev_seq and not is_node_reboot:
            if strict or not DEMO_MODE:
                log_security_event(
                    "REPLAY_SEQUENCE_DUPLICATE",
                    vid,
                    f"Duplicate or regressive sequence number #{seq} <= #{prev_seq}",
                    payload_str[:100],
                )
                return False, data, "REPLAY_SEQUENCE_DUPLICATE"

    # Record verified sequence number
    _record_sequence(vid, seq, packet_time)
    return True, data, "OK"
