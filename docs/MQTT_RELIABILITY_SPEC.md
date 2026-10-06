# V2V-SCADA MQTT Reliability & Architecture Specification

## 1. Architectural Strategy & Design Rationale

The MQTT layer in V2V-SCADA serves as the communication backbone between roadside infrastructure (RSU / Gateway Node), vehicle nodes, and the SCADA server.

### QoS 0 (At Most Once) Selection for High-Frequency Telemetry
- **Freshness Over Retransmission**: In vehicular safety (AIS-230 / SAE J2735), telemetry is broadcast at 10 Hz ($100\text{ ms}$ intervals). A packet becomes obsolete the moment a newer coordinate is sampled ($100\text{ ms}$ later).
- **Head-of-Line Blocking Prevention**: Utilizing QoS 1 or QoS 2 would force TCP/MQTT ACK roundtrips, queuing retransmissions and causing buffer bloat during RF packet loss.
- **Decision**: QoS 0 is used for high-frequency `v2v/telemetry`. Targeted alerts (`v2v/alerts/{vehicle_id}`) and commands utilize targeted publish with immediate broker dispatch.

### Zero-Broker Autonomous Direct-Dispatch Fallback
When Mosquitto is unreachable (e.g. offline bench test or single-node embedded deployment), `publish_or_dispatch` automatically switches to in-process memory dispatch. This guarantees that:
- The system never crashes or hangs on socket timeouts.
- Real-time collision physics calculations continue uninterrupted.
- When Mosquitto resumes, Paho MQTT automatically reconnects and restores network broadcast without server restart.

---

## 2. Topic Hierarchy

| Topic Pattern | Direction | QoS | Retained? | Description |
|:---|:---:|:---:|:---:|:---|
| **`v2v/telemetry`** | Edge $\rightarrow$ Backend | 0 | No | Inbound high-frequency signed vehicle telemetry frames. |
| **`v2v/gateway/health`** | Gateway $\rightarrow$ Backend | 0 | No | Roadside Gateway Node status, baud rate, and packet RX counters. |
| **`v2v/alerts/{vehicle_id}`**| Backend $\rightarrow$ Vehicle | 0 | No | Targeted collision alerts (TTC, closing speed, threat level). |
| **`v2v/commands`** | SCADA $\rightarrow$ Nodes | 1 | No | Supervisory override commands (e.g. speed advisory, lane caution). |

---

## 3. Disconnection & Reconnection State Machine

```
   [BOOT]
     │
     ▼
[CONNECTING] ───(Broker unreachable)───► [AUTONOMOUS DIRECT DISPATCH]
     │                                                ▲
 (rc == 0)                                            │ (rc != 0 on_disconnect)
     │                                                │
     ▼                                                │
 [CONNECTED] ─────────────────────────────────────────┘
     │ (Background loop_start auto-retries)
     ▼
[RECONNECTED] ───► [RESUBSCRIBE v2v/telemetry]
```

---

## 4. Security & Logging Guardrails
- **Credential Protection**: Usernames, passwords, and TLS private keys are never logged in plaintext.
- **Perimeter Cryptographic Validation**: Every packet ingested via MQTT passes HMAC-SHA256 signature and anti-replay verification before reaching internal vehicle state tables.
- **Throttled Alerts**: Alarms are rate-limited (`ALERT_RESEND_INTERVAL_SECONDS = 1.0s`) to prevent MQTT topic saturation during prolonged proximate hazards.
