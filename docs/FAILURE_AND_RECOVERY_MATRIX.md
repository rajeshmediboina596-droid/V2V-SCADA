# V2V-SCADA Failure & Recovery Classification Matrix

## Overview
This document evaluates the failure handling and recovery behavior of the V2V-SCADA system under adverse environmental, hardware, network, and software fault conditions. Every condition is strictly categorized into one of five states:
- **`REJECTED`**: Malformed or unauthentic data is blocked at the perimeter and prevented from entering the trusted collision engine.
- **`DEGRADED`**: System enters a graceful fallback mode (e.g. Rule-based TTC heuristic if ML offline; GPS course heading if IMU offline).
- **`RECOVERED`**: Subsystem resumes nominal operation automatically upon clearance of fault (e.g. MQTT reconnect, Node reboot sequence acceptance).
- **`FAIL-SAFE`**: Actuation hardware and outputs default to an inactive/safe posture (`AEB_RELAY = LOW / OFF`, buzzer silence).
- **`UNKNOWN`**: Indeterminate state requiring future mitigation.

---

## Comprehensive Failure & Recovery Matrix

| Condition | Injected Fault | Architectural Component | Observed System Behavior | Classification | Fail-Safe Posture |
|:---|:---|:---|:---|:---:|:---|
| **1. GNSS Signal Loss** | GNSS fix lost (`isValid() == false` / NMEA timeout) | STM32 / GPS UART2 | Sensor fusion freezes last known valid fix or halts broadcast; peer tracking continues. | **DEGRADED** | Relay remains OFF (`LOW`). No false positive AEB triggers. |
| **2. Invalid GNSS Coordinates** | NaN, `None`, or $\pm 180^\circ$ coordinate overflow | Backend Collision Engine | `compute_collision_risk` returns `(999.0m, 0.0m/s, risk_level=0, ttc=99.9s)`. | **FAIL-SAFE** | Safe return tuple prevents false collision alarm. |
| **3. IMU Failure** | MPU-6050 I2C NACK (Addr 0x68 disconnect) | STM32 I2C Driver | Sets `imuAvailable = false`, flags `ERR_IMU_OFFLINE`, falls back to GNSS Course over Ground. | **DEGRADED** | Fallback heading used; actuation outputs uninhibited. |
| **4. RF Communication Loss** | SX1281 signal loss or beacon dropout | STM32 Edge & SCADA | Telemetry timeout timer clears peer hazard after 2.5s; SCADA marks vehicle stale after 15s. | **FAIL-SAFE** | Stale hazard auto-cleared; relay forced `LOW`. |
| **5. MQTT Broker Disconnect** | Mosquitto broker stops or socket closes | Backend Bridge (`mqtt_client.py`) | Sets `is_mqtt_connected = False`; falls back dynamically to in-memory direct dispatch. | **DEGRADED** | Zero loss of collision computation for local nodes. |
| **6. MQTT Broker Reconnect** | Mosquitto broker restarts | Backend Client (`mqtt_client.py`) | Automatic reconnection via `on_connect` callback; resubscribes to `v2v/telemetry`. | **RECOVERED** | Seamless recovery without service restart. |
| **7. Database Unavailable** | SQLite lock contention or file permissions | Backend Storage (`database.py`) | In-memory `WRITE_QUEUE` buffers writes up to 10,000 items; health API reports `"degraded"`. | **DEGRADED** | Core real-time collision pipeline unaffected. |
| **8. WebSocket Disconnect** | Browser tab closed or network drop | FastAPI WebSocket Host | `WebSocketDisconnect` cleanly removes client from `connected_clients` set; zero thread leak. | **RECOVERED** | Browser auto-reconnects with exponential backoff. |
| **9. Malformed Telemetry** | Truncated JSON / invalid syntax | Perimeter Ingest (`security.py`) | JSON decode exception caught; logs `MALFORMED_JSON` to security audit; drops packet. | **REJECTED** | Packet never reaches collision physics engine. |
| **10. HMAC Verification Failure** | Tampered coordinates, speed, or rogue key | Perimeter Ingest (`security.py`) | Constant-time `compare_digest` fails; logs `HMAC_SIGNATURE_MISMATCH`; drops packet. | **REJECTED** | Spoofed packet discarded at edge and gateway. |
| **11. Timestamp Expired** | Stale packet delayed by $> 30\text{ seconds}$ | Anti-Replay Guard (`security.py`)| Clock skew check exceeds tolerance; logs `TIMESTAMP_EXPIRED`; drops packet. | **REJECTED** | Replay of historical packets strictly blocked. |
| **12. Repeated Sequence Number** | Duplicate packet with $\text{seq}_n \le \text{seq}_{n-1}$| Anti-Replay Guard (`security.py`)| Monotonic tracker detects duplicate/regression; logs `REPLAY_SEQUENCE_DUPLICATE`; drops packet.| **REJECTED** | Replay attack prevented. |
| **13. Microcontroller Reboot** | Node restarts ($\text{seq} \le 5$, prev $> 10$) | Anti-Replay Guard (`security.py`)| Detects reboot signature ($\text{seq} \le 5$ and $t \ge t_{\text{last}}$); resets sequence counter.| **RECOVERED** | Allows node to rejoin network after power cycle. |
| **14. ML Model Missing / Corrupted**| Pickled classifier file missing | ML Layer (`collision_model.py`) | Detects missing file; logs warning; activates deterministic ISO 15623 rule-based TTC heuristic.| **DEGRADED** | Zero collision assessment interruption. |

---

## Prototype AEB Relay Safety Assessment
The prototype Automatic Emergency Braking (AEB) relay (`PIN_AEB_RELAY`, PB9 on STM32) represents an active physical output. Its safety posture is enforced as follows:
1. **Startup Default**: Configured as `pinMode(PIN_AEB_RELAY, OUTPUT)` and explicitly driven `LOW` during `setup()`.
2. **Reset Default**: Microcontroller reset sets all GPIOs to High-Impedance (Hi-Z), keeping the active-high relay driver de-energized.
3. **Communication Loss**: An internal timeout timer (`millis() - lastPeerPacketTime > 2500`) auto-clears any active critical alert and forces `PIN_AEB_RELAY` to `LOW`.
4. **Sensor & Ingest Failure**: Corrupted JSON, HMAC failures, and GNSS invalidity return immediately, preventing relay actuation.

> [!CAUTION]
> **Laboratory Demonstration Warning**:
> This platform implements an engineering prototype collision assessment system. The AEB relay actuation is intended solely for bench-level LED and bench relay demonstration. It must NEVER be connected to a physical vehicle's hydraulic or brake-by-wire system without ASIL-D certified hardware redundancy and formal homologation.
