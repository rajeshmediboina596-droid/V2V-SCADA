# V2V-SCADA Canonical Telemetry Contract (v1.0)

## Overview & Scope
This document defines the single, authoritative data contract for all vehicular telemetry exchanged within the V2V-SCADA platform. Every component in the system—including STM32 edge firmware, 2.4 GHz RF transceivers, serial USB gateway bridges, Mosquitto MQTT broker, FastAPI backend, SQLite persistent storage, and Leaflet SCADA HUD—MUST strictly adhere to this schema and its semantics.

---

## 1. Field Specification & Data Dictionary

| Field Name | Type | Unit | Range / Constraints | Required? | Semantics & Automotive Description |
|:---|:---:|:---:|:---:|:---:|:---|
| **`vehicle_id`** | `String` | — | 1–32 ASCII chars (`[A-Za-z0-9_-]+`) | **REQUIRED** | Unique broadcast identity of the vehicle node (e.g. `"V1"`, `"EMERGENCY_AMB_01"`). |
| **`vehicle_type`** | `String` | — | `"Passenger"`, `"Truck"`, `"Emergency"` | **REQUIRED** | Classification of vehicle chassis. `"Emergency"` triggers threat level 4 preemption. |
| **`timestamp`** | `Integer` | Seconds | Unix Epoch ($> 1700000000$) | **REQUIRED** | Time of sensor sampling at the edge node. Skew checked within $\pm 30$ seconds. |
| **`seq`** | `Integer` | Count | $0 \le \text{seq} \le 2^{32}-1$ | **REQUIRED** | Monotonically increasing sequence number. Incremented by 1 per 10Hz transmission. |
| **`lat`** | `Float` | Degrees | $-90.000000 \le \phi \le +90.000000$ | **REQUIRED** | WGS-84 Geodetic Latitude. Serialized with 6 decimal places ($\sim 0.11\text{ m}$ precision). |
| **`lon`** | `Float` | Degrees | $-180.000000 \le \lambda \le +180.000000$ | **REQUIRED** | WGS-84 Geodetic Longitude. Serialized with 6 decimal places ($\sim 0.11\text{ m}$ precision). |
| **`alt`** | `Float` | Meters | $-500.0 \le h \le +10000.0$ | Optional | Altitude above mean sea level from GNSS receiver. |
| **`speed_kmph`** | `Float` | km/h | $0.0 \le v \le 250.0$ | **REQUIRED** | Ground speed over earth surface. Converted internally to $\text{m/s}$ ($v_{\text{mps}} = v / 3.6$) for TTC. |
| **`heading_deg`** | `Float` | Degrees | $0.0 \le \theta < 360.0$ | **REQUIRED** | Compass course over ground. $0^\circ = \text{North}$, $90^\circ = \text{East}$, $180^\circ = \text{South}$, $270^\circ = \text{West}$. |
| **`pitch_deg`** | `Float` | Degrees | $-90.0 \le \alpha \le +90.0$ | Optional | Vehicle chassis inclination along longitudinal axis (MPU-6050 accelerometer). |
| **`roll_deg`** | `Float` | Degrees | $-90.0 \le \beta \le +90.0$ | Optional | Vehicle chassis roll angle along transverse axis (MPU-6050 accelerometer). |
| **`yaw_deg`** | `Float` | Degrees | $0.0 \le \gamma < 360.0$ | Optional | Vehicle heading rate/course (fused with GNSS course). |
| **`battery_level`**| `Float` | % | $0.0 \le \text{SOC} \le 100.0$ | Optional | DC bus 12V vehicle battery state of charge (ADC sampling). |
| **`emergency_status`**| `Integer`| Flag | $0$ (Normal) or $1$ (Active Siren) | **REQUIRED** | Immediate flag indicating active priority vehicle right-of-way. |
| **`rf_status`** | `String` | — | `"OK"`, `"DEGRADED"`, `"OFFLINE"` | Optional | Transceiver self-health diagnostic status. |
| **`fault_code`** | `String` | — | `"NONE"`, `"ERR_IMU_OFFLINE"`, etc. | Optional | Diagnostic Trouble Code (DTC) from on-board self-test. |
| **`signature`** | `String` | Hex | 64 lowercase hexadecimal characters | **REQUIRED** | Cryptographic HMAC-SHA256 signature of canonical signing string. |

---

## 2. Canonical Signing Representation & HMAC Specification

To prevent data serialization ambiguity and ensure byte-level determinism between C++ (`ArduinoJson` / `SHA256.h`) and Python (`hashlib` / `hmac`), the cryptographic signature is calculated over an explicit, delimited canonical string:

```text
vehicle_id={vid}|vehicle_type={vtype}|timestamp={ts}|seq={seq}|lat={lat:.6f}|lon={lon:.6f}|speed_kmph={speed:.1f}|heading_deg={int(round(heading))}
```

### Deterministic Formatting Rules
1. **`lat` / `lon`**: Formatted with exactly 6 decimal places (e.g. `17.423900`).
2. **`speed_kmph`**: Formatted with exactly 1 decimal place (e.g. `42.5`).
3. **`heading_deg`**: Formatted as integer degrees rounded to nearest whole number (e.g. `90`).
4. **`seq`**: Formatted as decimal integer string with no leading zeroes.
5. **`timestamp`**: Formatted as integer Unix seconds string.
6. **No Spaces**: Keys and values are separated by `=` and items by `|` with zero extraneous whitespace.

---

## 3. JSON Wire Frame Example

```json
{
  "vehicle_id": "V1",
  "vehicle_type": "Passenger",
  "timestamp": 1730000100,
  "seq": 42,
  "lat": 17.423900,
  "lon": 78.448300,
  "alt": 542.0,
  "speed_kmph": 45.0,
  "heading_deg": 90.0,
  "pitch_deg": 0.5,
  "roll_deg": -0.2,
  "yaw_deg": 90.0,
  "battery_level": 98.5,
  "emergency_status": 0,
  "rf_status": "OK",
  "fault_code": "NONE",
  "signature": "304655f46eb2c64032d8478d1f70a59a722ea05b22b2ee2d80d297ff05b76cf6"
}
```

---

## 4. Sequence & Anti-Replay Semantics
- **Monotonicity**: Each transmitted packet for a vehicle must contain $\text{seq}_{n} > \text{seq}_{n-1}$.
- **Reboot Detection**: If a vehicle microcontroller reboots, sequence resets to $\text{seq} \le 5$. The receiver accepts this transition only if $\text{timestamp} \ge \text{timestamp}_{\text{last}}$.
- **Sliding Window**: Packets whose timestamps deviate by more than $\pm 30\text{ seconds}$ from system clock are dropped as expired or desynchronized.
